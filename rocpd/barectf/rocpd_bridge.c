// --- file: barectf/rocpd_bridge.c ---
/*
 * Tiny bridge which uses the generated tracer (barectf/gen) and the Linux FS demo platform.
 * Adjust include paths/names to match your clone of the platform. The only platform requirement
 * is that it exposes (or you add) a way to set the default clock value the tracer reads.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "rocpd_bridge.h"

/* Generated headers (from `barectf gen`) */
#include "barectf.h"

/* Demo platform headers (from the barectf linux-fs example) */
#include "barectf-platform-linux-fs/barectf-platform-linux-fs.h"

static struct barectf_platform_linux_fs_ctx* pctx = NULL;         /* platform ctx */
static struct barectf_default_ctx* sctx = NULL;                     /* DS ctx (name = rocpd) */

int rocpd_init(const char* out_dir, uint32_t target_packet_bytes)
{
    if (pctx) return 0;
    /* Initialize platform: packet size, output dir, trace file base name, overwrite=0, sync=0 */
    pctx = barectf_platform_linux_fs_init(target_packet_bytes, out_dir, 0, 0, 0);
    if (!pctx) return -1;
    sctx = barectf_platform_linux_fs_get_barectf_ctx(pctx);
    return sctx ? 0 : -2;
}

void rocpd_close(void)
{
    if (pctx) {
        barectf_platform_linux_fs_fini(pctx);
        pctx = NULL; sctx = NULL;
    }
}

/* Set clock for next event */
void rocpd_set_clock(uint64_t timestamp_ns)
{
    barectf_platform_linux_fs_set_clock(timestamp_ns);
}

/* Generic region event writer; selects barectf event by id */
void rocpd_trace_region(
    uint16_t event_id,
    int64_t region_id, const char* guid, const char* name, const char* category,
    int64_t nid, int64_t pid, int64_t tid, int64_t event_internal_id,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id,
    int64_t duration, const char* extdata, const char* call_stack, const char* line_info,
    uint64_t timestamp_ns)
{
    if (!sctx) return;
    rocpd_set_clock(timestamp_ns);
    switch (event_id) {
        case 12: barectf_trace_hip_runtime_region_event_start(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 13: barectf_trace_hip_runtime_region_event_end(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 15: barectf_trace_hip_compiler_region_event_start(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 16: barectf_trace_hip_compiler_region_event_end(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 18: barectf_trace_hsa_core_region_event_start(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 19: barectf_trace_hsa_core_region_event_end(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 21: barectf_trace_hsa_amd_ext_region_event_start(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 22: barectf_trace_hsa_amd_ext_region_event_end(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        case 24: barectf_trace_marker_core_region_event_start(sctx, region_id, guid?guid:"", name?name:"", category?category:"", nid, pid, tid, event_internal_id, stack_id, parent_stack_id, correlation_id, duration, extdata?extdata:"", call_stack?call_stack:"", line_info?line_info:""); break;
        default: break; /* ignore */
    }
}

void rocpd_trace_memory_allocation(
    uint16_t event_id, int64_t allocation_id, const char* guid, const char* category,
    int64_t nid, int64_t pid, int64_t tid, const char* allocation_type, const char* level, const char* agent_name,
    int64_t agent_abs_index, int64_t agent_log_index, int64_t agent_type_index, const char* agent_type,
    int64_t address, int64_t size, int64_t queue_id, const char* queue_name, int64_t stream_id, const char* stream_name,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id, int64_t duration, uint64_t timestamp_ns)
{
    if (!sctx) return; rocpd_set_clock(timestamp_ns);
    if (event_id == 9) {
        barectf_trace_memory_allocation_event_start(sctx, allocation_id, guid?guid:"", category?category:"", nid, pid, tid, allocation_type?allocation_type:"", level?level:"", agent_name?agent_name:"", agent_abs_index, agent_log_index, agent_type_index, agent_type?agent_type:"", address, size, queue_id, queue_name?queue_name:"", stream_id, stream_name?stream_name:"", stack_id, parent_stack_id, correlation_id, duration);
    } else if (event_id == 10) {
        barectf_trace_memory_allocation_event_end(sctx, allocation_id, guid?guid:"", category?category:"", nid, pid, tid, allocation_type?allocation_type:"", level?level:"", agent_name?agent_name:"", agent_abs_index, agent_log_index, agent_type_index, agent_type?agent_type:"", address, size, queue_id, queue_name?queue_name:"", stream_id, stream_name?stream_name:"", stack_id, parent_stack_id, correlation_id, duration);
    }
}

void rocpd_trace_memory_copy(
    uint16_t event_id, int64_t copy_id, const char* guid, const char* category,
    int64_t nid, int64_t pid, int64_t tid, const char* name, const char* region_name, int64_t stream_id, int64_t queue_id,
    const char* stream_name, const char* queue_name, int64_t size, const char* dst_device, int64_t dst_agent_abs_index, int64_t dst_agent_log_index,
    int64_t dst_agent_type_index, const char* dst_agent_type, int64_t dst_address, const char* src_device, int64_t src_agent_abs_index,
    int64_t src_agent_log_index, int64_t src_agent_type_index, const char* src_agent_type, int64_t src_address,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id, int64_t duration, uint64_t timestamp_ns)
{
    if (!sctx) return; rocpd_set_clock(timestamp_ns);
    if (event_id == 6) {
        barectf_trace_memory_copy_event_start(sctx, copy_id, guid?guid:"", category?category:"", nid, pid, tid, name?name:"", region_name?region_name:"", stream_id, queue_id, stream_name?stream_name:"", queue_name?queue_name:"", size, dst_device?dst_device:"", dst_agent_abs_index, dst_agent_log_index, dst_agent_type_index, dst_agent_type?dst_agent_type:"", dst_address, src_device?src_device:"", src_agent_abs_index, src_agent_log_index, src_agent_type_index, src_agent_type?src_agent_type:"", src_address, stack_id, parent_stack_id, correlation_id, duration);
    } else if (event_id == 7) {
        barectf_trace_memory_copy_event_end(sctx, copy_id, guid?guid:"", category?category:"", nid, pid, tid, name?name:"", region_name?region_name:"", stream_id, queue_id, stream_name?stream_name:"", queue_name?queue_name:"", size, dst_device?dst_device:"", dst_agent_abs_index, dst_agent_log_index, dst_agent_type_index, dst_agent_type?dst_agent_type:"", dst_address, src_device?src_device:"", src_agent_abs_index, src_agent_log_index, src_agent_type_index, src_agent_type?src_agent_type:"", src_address, stack_id, parent_stack_id, correlation_id, duration);
    }
}

void rocpd_trace_kernel_dispatch(
    uint16_t event_id, int64_t kernel_id, const char* guid, int64_t tid, const char* category, const char* region,
    const char* name, int64_t nid, int64_t pid, int64_t agent_abs_index, int64_t agent_log_index, int64_t agent_type_index, const char* agent_type,
    int64_t code_object_id, int64_t kernel_symbol_id, int64_t dispatch_id, int64_t stream_id, int64_t queue_id, const char* queue_name, const char* stream_name,
    int64_t grid_size_x, int64_t grid_size_y, int64_t grid_size_z, int64_t workgroup_size_x, int64_t workgroup_size_y, int64_t workgroup_size_z,
    int64_t lds_size, int64_t scratch_size, int64_t static_lds_size, int64_t static_scratch_size,
    int64_t stack_id, int64_t parent_stack_id, int64_t correlation_id, int64_t duration, uint64_t timestamp_ns)
{
    if (!sctx) return; rocpd_set_clock(timestamp_ns);
    if (event_id == 3) {
        barectf_trace_kernel_dispatch_event_start(sctx, kernel_id, guid?guid:"", tid, category?category:"", region?region:"", name?name:"", nid, pid, agent_abs_index, agent_log_index, agent_type_index, agent_type?agent_type:"", code_object_id, kernel_symbol_id, dispatch_id, stream_id, queue_id, queue_name?queue_name:"", stream_name?stream_name:"", grid_size_x, grid_size_y, grid_size_z, workgroup_size_x, workgroup_size_y, workgroup_size_z, lds_size, scratch_size, static_lds_size, static_scratch_size, stack_id, parent_stack_id, correlation_id, duration);
    } else if (event_id == 4) {
        barectf_trace_kernel_dispatch_event_end(sctx, kernel_id, guid?guid:"", tid, category?category:"", region?region:"", name?name:"", nid, pid, agent_abs_index, agent_log_index, agent_type_index, agent_type?agent_type:"", code_object_id, kernel_symbol_id, dispatch_id, stream_id, queue_id, queue_name?queue_name:"", stream_name?stream_name:"", grid_size_x, grid_size_y, grid_size_z, workgroup_size_x, workgroup_size_y, workgroup_size_z, lds_size, scratch_size, static_lds_size, static_scratch_size, stack_id, parent_stack_id, correlation_id, duration);
    }
}

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
    int64_t code_object_id, uint64_t timestamp_ns)
{
    if (!sctx) return; rocpd_set_clock(timestamp_ns);
    barectf_trace_counter_collection_event(sctx, id, guid?guid:"", dispatch_id, kernel_id, event_id, correlation_id, stack_id, parent_stack_id, pid, tid, agent_id, agent_abs_index, agent_log_index, agent_type_index, agent_type?agent_type:"", queue_id, grid_size_x, grid_size_y, grid_size_z, name?name:"", kernel_region?kernel_region:"", workgroup_size_x, workgroup_size_y, workgroup_size_z, lds_block_size, scratch_size, vgpr_count, accum_vgpr_count, sgpr_count, counter_name?counter_name:"", counter_symbol?counter_symbol:"", component?component:"", description?description:"", block?block:"", expression?expression:"", value_type?value_type:"", counter_id, value, start, end, is_constant, is_derived, duration, category?category:"", nid, extdata?extdata:"", code_object_id);
}

/* Notes:
 * - Function names barectf_rocpd_trace_XXX() come from the YAML: data-stream name = rocpd,
 *   event-record type names = api/kernel_dispatch/memcpy. If you rename them, adjust here.
 * - The linux-fs platform API above (create/get_barectf_ctx/set_current_clock_value/destroy)
 *   matches the demo platform shipped with the docs; if your clone differs, adapt calls.
 */