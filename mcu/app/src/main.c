#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

LOG_MODULE_REGISTER(havoc_mcu, LOG_LEVEL_INF);

#define COUNTER_STACK_SIZE 1024
#define COUNTER_PRIORITY   5
#define COUNTER_PERIOD_MS  100

static void counter_thread(void *p1, void *p2, void *p3)
{
	ARG_UNUSED(p1);
	ARG_UNUSED(p2);
	ARG_UNUSED(p3);

	uint32_t count = 0;
	while (1) {
		LOG_INF("count=%u", count++);
		k_sleep(K_MSEC(COUNTER_PERIOD_MS));
	}
}

K_THREAD_DEFINE(counter_tid, COUNTER_STACK_SIZE, counter_thread,
		NULL, NULL, NULL, COUNTER_PRIORITY, 0, 0);

int main(void)
{
	LOG_INF("havoc_mcu starting");
	return 0;
}
