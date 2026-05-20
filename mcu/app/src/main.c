#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include <string.h>

#include <rcl/rcl.h>
#include <rcl/error_handling.h>
#include <rclc/rclc.h>
#include <rclc/executor.h>
#include <rmw_microros/rmw_microros.h>
#include <std_msgs/msg/int32.h>

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

static rcl_publisher_t publisher;
static std_msgs__msg__Int32 msg;

static void timer_callback(rcl_timer_t *timer, int64_t last_call_time)
{
	ARG_UNUSED(last_call_time);
	if (timer == NULL) {
		return;
	}
	RCSOFTCHECK(rcl_publish(&publisher, &msg, NULL));
	LOG_INF("published count=%d", msg.data);
	msg.data++;
}

int main(void)
{
	LOG_INF("havoc_mcu starting (micro-ROS Int32 publisher)");

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
		&publisher,
		&node,
		ROSIDL_GET_MSG_TYPE_SUPPORT(std_msgs, msg, Int32),
		"havoc_counter"));

	rcl_timer_t timer;
	RCCHECK(rclc_timer_init_default(
		&timer,
		&support,
		RCL_MS_TO_NS(1000),
		timer_callback));

	rclc_executor_t executor;
	RCCHECK(rclc_executor_init(&executor, &support.context, 1, &allocator));
	RCCHECK(rclc_executor_add_timer(&executor, &timer));

	msg.data = 0;

	while (1) {
		rclc_executor_spin_some(&executor, RCL_MS_TO_NS(100));
		k_sleep(K_MSEC(100));
	}

	return 0;
}
