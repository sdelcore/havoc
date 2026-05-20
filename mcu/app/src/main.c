#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

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

static rcl_publisher_t counter_pub;
static std_msgs__msg__Int32 counter_msg;

static rcl_subscription_t cmd_vel_sub;
static geometry_msgs__msg__Twist cmd_vel_msg;

static void timer_callback(rcl_timer_t *timer, int64_t last_call_time)
{
	ARG_UNUSED(last_call_time);
	if (timer == NULL) {
		return;
	}
	RCSOFTCHECK(rcl_publish(&counter_pub, &counter_msg, NULL));
	counter_msg.data++;
}

static void cmd_vel_callback(const void *msgin)
{
	const geometry_msgs__msg__Twist *m = msgin;
	// Real firmware will translate this to PWM. For M5, just log what
	// arrived - proves the wire path from ROS through the agent to here.
	LOG_INF("cmd_vel: linear.x=%f angular.z=%f",
		m->linear.x, m->angular.z);
}

int main(void)
{
	LOG_INF("havoc_mcu starting (micro-ROS publisher + cmd_vel subscriber)");

	// default_params is defined in microros_transports.h with a hardcoded
	// "192.168.1.100" - the upstream module's Kconfig knob doesn't actually
	// propagate to the transport's default_params struct. Override here
	// from CONFIG_MICROROS_AGENT_IP / _PORT so prj.conf is the source of
	// truth.
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

	// Executor needs one handle slot per timer + subscription. We have
	// one of each, so reserve 2.
	rclc_executor_t executor;
	RCCHECK(rclc_executor_init(&executor, &support.context, 2, &allocator));
	RCCHECK(rclc_executor_add_timer(&executor, &timer));
	RCCHECK(rclc_executor_add_subscription(
		&executor, &cmd_vel_sub, &cmd_vel_msg,
		cmd_vel_callback, ON_NEW_DATA));

	counter_msg.data = 0;

	while (1) {
		rclc_executor_spin_some(&executor, RCL_MS_TO_NS(100));
		k_sleep(K_MSEC(100));
	}

	return 0;
}
