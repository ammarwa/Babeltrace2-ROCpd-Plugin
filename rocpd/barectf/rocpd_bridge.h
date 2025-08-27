// --- file: barectf/rocpd_bridge.h ---
/* Minimal C bridge: expose a stable C API for Python (ctypes) and hide barectf details. */
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Create a trace in `out_dir` with a target packet size (bytes). Returns 0 on success. */
int rocpd_init(const char* out_dir, uint32_t target_packet_bytes);
void rocpd_close(void);

/* Set trace clock (ns) before emitting event to reflect DB timestamp */
void rocpd_set_clock(uint64_t timestamp_ns);

/* Event writers — parameters mirror the YAML payload fields. */
/* Region style events (start/end, various domains). All share identical payload schema. */
void rocpd_trace_region(
    uint16_t event_id, /* one of 12,13,15,16,18,19,21,22,24 */
    int64_t region_id, const char* guid, const char* name, const char* category,
    int64_t nid, int64_t pid, int64_t tid, int64_t event_internal_id,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id,
    int64_t duration, const char* extdata, const char* call_stack, const char* line_info,
    uint64_t timestamp_ns);

/* Memory allocation events */
void rocpd_trace_memory_allocation(
    uint16_t event_id, /* 9=start 10=end */
    int64_t allocation_id, const char* guid, const char* category,
    int64_t nid, int64_t pid, int64_t tid,
    const char* allocation_type, const char* level, const char* agent_name,
    int64_t agent_abs_index, int64_t agent_log_index, int64_t agent_type_index, const char* agent_type,
    int64_t address, int64_t size, int64_t queue_id, const char* queue_name,
    int64_t stream_id, const char* stream_name, int64_t stack_id, int64_t parent_stack_id,
    int64_t correlation_id, int64_t duration, uint64_t timestamp_ns);

/* Memory copy events */
void rocpd_trace_memory_copy(
    uint16_t event_id, /* 6=start 7=end */
    int64_t copy_id, const char* guid, const char* category,
    int64_t nid, int64_t pid, int64_t tid, const char* name, const char* region_name,
    int64_t stream_id, int64_t queue_id, const char* stream_name, const char* queue_name,
    int64_t size, const char* dst_device, int64_t dst_agent_abs_index, int64_t dst_agent_log_index,
    int64_t dst_agent_type_index, const char* dst_agent_type, int64_t dst_address,
    const char* src_device, int64_t src_agent_abs_index, int64_t src_agent_log_index,
    int64_t src_agent_type_index, const char* src_agent_type, int64_t src_address,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id, int64_t duration,
    uint64_t timestamp_ns);

/* Kernel dispatch events */
void rocpd_trace_kernel_dispatch(
    uint16_t event_id, /* 3=start 4=end */
    int64_t kernel_id, const char* guid, int64_t tid, const char* category, const char* region,
    const char* name, int64_t nid, int64_t pid, int64_t agent_abs_index, int64_t agent_log_index,
    int64_t agent_type_index, const char* agent_type, int64_t code_object_id, int64_t kernel_symbol_id,
    int64_t dispatch_id, int64_t stream_id, int64_t queue_id, const char* queue_name, const char* stream_name,
    int64_t grid_size_x, int64_t grid_size_y, int64_t grid_size_z,
    int64_t workgroup_size_x, int64_t workgroup_size_y, int64_t workgroup_size_z,
    int64_t lds_size, int64_t scratch_size, int64_t static_lds_size, int64_t static_scratch_size,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id, int64_t duration,
    uint64_t timestamp_ns);

/* Counter collection event */
void rocpd_trace_counter_collection(
    int64_t id, const char* guid, int64_t dispatch_id, int64_t kernel_id, int64_t event_id,
    int64_t correlation_id, int64_t stack_id, int64_t parent_stack_id, int64_t pid, int64_t tid,
    int64_t agent_id, int64_t agent_abs_index, int64_t agent_log_index, int64_t agent_type_index,
    const char* agent_type, int64_t queue_id, int64_t grid_size_x, int64_t grid_size_y, int64_t grid_size_z,
    const char* name, const char* kernel_region, int64_t workgroup_size_x, int64_t workgroup_size_y, int64_t workgroup_size_z,
    int64_t lds_block_size, int64_t scratch_size, int64_t vgpr_count, int64_t accum_vgpr_count, int64_t sgpr_count,
    const char* counter_name, const char* counter_symbol, const char* component, const char* description, const char* block,
    const char* expression, const char* value_type, int64_t counter_id, double value, int64_t start, int64_t end,
    int64_t is_constant, int64_t is_derived, int64_t duration, const char* category, int64_t nid, const char* extdata,
    int64_t code_object_id, uint64_t timestamp_ns);

#ifdef __cplusplus
}
#endif