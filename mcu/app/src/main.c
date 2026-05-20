#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/atomic.h>

#include <string.h>

#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <rmw_microros/rmw_microros.h>
#include <std_msgs/msg/int32.h>
#include <geometry_msgs/msg/twist.h>

#include <microros_transports.h>

LOG_MODULE_REGISTER(havoc_mcu, LOG_LEVEL_INF);

#define RCCHECK(fn) { \
	rcl_ret_t _rc = (fn); \
	if (_rc != RCL_RET_OK) { \
		LOG_ERR("rcl failed line %d rc=%d - halting", __LINE__, (int)_rc); \
		for (;;) { k_sleep(K_FOREVER); } \
	} \
}

#define RCSOFTCHECK(fn) { \
	rcl_ret_t _rc = (fn); \
	if (_rc != RCL_RET_OK) { \
		LOG_WRN("rcl soft-fail line %d rc=%d", __LINE__, (int)_rc); \
	} \
}

// --- micro-ROS handles -------------------------------------------------

static rcl_publisher_t counter_pub;
static std_msgs__msg__Int32 counter_msg;

static rcl_subscription_t cmd_vel_sub;
static geometry_msgs__msg__Twist cmd_vel_msg;

// /havoc_cmd_actual: what the firmware is actually driving after the
// watchdog has its say. ROS subscribes here to see real behavior - in
// stall this is zero even if /cmd_vel is still being published.
static rcl_publisher_t cmd_actual_pub;
static geometry_msgs__msg__Twist cmd_actual_msg;

// --- Stall watchdog ----------------------------------------------------
// Architectural promise: if cmd_vel stops arriving, zero the throttle.
// The companion (Pi / Orin) can crash, the ROS graph can deadlock, the
// network can drop - the car should coast to a stop, not run open-loop.

#define STALL_THRESHOLD_MS  200
#define WATCHDOG_PERIOD_MS   50

// 32-bit millisecond timestamp from k_uptime_get_32. Atomic reads/writes
// on 32-bit values are inherently safe on all Zephyr-supported arches,
// so atomic_t (which is sized for the pointer width) is more than enough.
static atomic_t last_cmd_vel_ms;

// The current commanded throttle. On real hardware this will be a PWM
// duty cycle written to the ESC; for now it's just a value the watchdog
// can zero.
static float current_throttle = 0.0f;
static float current_steering = 0.0f;

// Has the watchdog already logged that we're in a stall? Prevents
// spamming the log every WATCHDOG_PERIOD_MS while stalled.
static bool watchdog_in_stall = false;

static void watchdog_check(struct k_timer *timer)
{
	ARG_UNUSED(timer);

	uint32_t last = (uint32_t)atomic_get(&last_cmd_vel_ms);
	uint32_t now = k_uptime_get_32();
	uint32_t age_ms = now - last;

	if (age_ms > STALL_THRESHOLD_MS) {
		current_throttle = 0.0f;
		current_steering = 0.0f;
		if (!watchdog_in_stall) {
			watchdog_in_stall = true;
			LOG_WRN("STALL - throttle zeroed (no cmd_vel for %u ms)",
				age_ms);
		}
	} else if (watchdog_in_stall) {
		watchdog_in_stall = false;
		LOG_INF("cmd_vel recovered, watchdog clear");
	}
}

K_TIMER_DEFINE(watchdog_timer, watchdog_check, NULL);

// --- ROS callbacks -----------------------------------------------------

static void timer_callback(rcl_timer_t *timer, int64_t last_call_time)
{
	ARG_UNUSED(last_call_time);
	if (timer == NULL) {
		return;
	}
	RCSOFTCHECK(rcl_publish(&counter_pub, &counter_msg, NULL));
	counter_msg.data++;
}

static void cmd_actual_timer_callback(rcl_timer_t *timer, int64_t last_call_time)
{
	ARG_UNUSED(last_call_time);
	if (timer == NULL) {
		return;
	}
	// current_throttle / current_steering are kept zero by the watchdog
	// when /cmd_vel has stalled, so publishing them gives ROS the
	// post-watchdog view of what the firmware is driving.
	cmd_actual_msg.linear.x = current_throttle;
	cmd_actual_msg.angular.z = current_steering;
	RCSOFTCHECK(rcl_publish(&cmd_actual_pub, &cmd_actual_msg, NULL));
}

static void cmd_vel_callback(const void *msgin)
{
	const geometry_msgs__msg__Twist *m = msgin;

	// Latch the commanded values - what the firmware would drive if no
	// stall. The watchdog reads/writes these from a separate context.
	current_throttle = (float)m->linear.x;
	current_steering = (float)m->angular.z;

	// Mark "alive" for the watchdog. Order matters: the assignments
	// above happen before the watchdog can possibly clear them on its
	// next tick (worst case ~WATCHDOG_PERIOD_MS later).
	atomic_set(&last_cmd_vel_ms, (atomic_val_t)k_uptime_get_32());
}

int main(void)
{
	LOG_INF("havoc_mcu starting (publisher + cmd_vel subscriber + watchdog)");

	// Bootstrap the watchdog timestamp to "now" so the watchdog doesn't
	// fire immediately at startup before any cmd_vel has arrived.
	atomic_set(&last_cmd_vel_ms, (atomic_val_t)k_uptime_get_32());

	strncpy(default_params.ip, CONFIG_MICROROS_AGENT_IP,
		sizeof(default_params.ip) - 1);
	strncpy(default_params.port, CONFIG_MICROROS_AGENT_PORT,
		sizeof(default_params.port) - 1);
	LOG_INF("agent target: %s:%s", default_params.ip, default_params.port);

	rmw_uros_set_custom_transport(
		MICRO_ROS_FRAMING_REQUIRED,
		(void *)&default_params,
		zephyr_transport_open,
		zephyr_transport_close,
		zephyr_transport_write,
		zephyr_transport_read);

	rcl_allocator_t allocator = rcl_get_default_allocator();
	rclc_support_t support;
	RCCHECK(rclc_support_init(&support, 0, NULL, &allocator));

	rcl_node_t node;
	RCCHECK(rclc_node_init_default(&node, "havoc_mcu", "", &support));

	RCCHECK(rclc_publisher_init_default(
		&counter_pub,
		&node,
		ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
		"havoc_counter"));

	RCCHECK(rclc_publisher_init_default(
		&cmd_actual_pub,
		&node,
		ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
		"havoc_cmd_actual"));

	RCCHECK(rclc_subscription_init_default(
		&cmd_vel_sub,
		&node,
		ROSIDL_GET_MSG_TYPE_SUPPORT(geometry_msgs, msg, Twist),
		"cmd_vel"));

	rcl_timer_t timer;
	RCCHECK(rclc_timer_init_default(
		&timer,
		&support,
		RCL_MS_TO_NS(1000),
		timer_callback));

	rcl_timer_t cmd_actual_timer;
	RCCHECK(rclc_timer_init_default(
		&cmd_actual_timer,
		&support,
		RCL_MS_TO_NS(100),   // 10 Hz status echo
		cmd_actual_timer_callback));

	// Executor: counter_timer + cmd_actual_timer + cmd_vel_sub = 3 slots.
	rclc_executor_t executor;
	RCCHECK(rclc_executor_init(&executor, &support.context, 3, &allocator));
	RCCHECK(rclc_executor_add_timer(&executor, &timer));
	RCCHECK(rclc_executor_add_timer(&executor, &cmd_actual_timer));
	RCCHECK(rclc_executor_add_subscription(
		&executor, &cmd_vel_sub, &cmd_vel_msg,
		cmd_vel_callback, ON_NEW_DATA));

	counter_msg.data = 0;

	// Start the watchdog. Fires every WATCHDOG_PERIOD_MS, no initial
	// delay. The reload arg matches the duration so it runs forever.
	k_timer_start(&watchdog_timer,
		      K_MSEC(WATCHDOG_PERIOD_MS),
		      K_MSEC(WATCHDOG_PERIOD_MS));

	while (1) {
		rclc_executor_spin_some(&executor, RCL_MS_TO_NS(100));
		k_sleep(K_MSEC(100));
	}

	return 0;
}
