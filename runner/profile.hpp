// Laboratory-only observation; no changes to Script, flags, or budget decisions.
#ifndef GSR_LAB_PROFILE_HPP
#define GSR_LAB_PROFILE_HPP
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <univalue/include/univalue.h>
#include <script/varops.h>
struct GsrProfile {
    bool enabled{true};
    uint64_t stack_entries{}, stack_bytes{}, total_entries{}, total_bytes{}, max_item{};
    uint64_t function_storage{}, executed_bodies{}, invocations{}, sha_calls{}, sha_compressions{};
    std::array<uint64_t,256> opcodes{}, function_calls{}, function_varops{};
    UniValue Json(uint64_t ns) const {
        UniValue r{UniValue::VOBJ};
        r.pushKV("interpreter_ns",ns);
        r.pushKV("observations_enabled",enabled);
        r.pushKV("peak_stack_entries",stack_entries); r.pushKV("peak_stack_bytes",stack_bytes);
        r.pushKV("peak_total_entries",total_entries); r.pushKV("peak_total_bytes",total_bytes);
        r.pushKV("max_item_bytes",max_item); r.pushKV("function_storage_bytes",function_storage);
        r.pushKV("executed_function_body_bytes",executed_bodies); r.pushKV("invocations",invocations);
        r.pushKV("sha256_calls",sha_calls); r.pushKV("sha256_compressions",sha_compressions);
        UniValue ops{UniValue::VOBJ}, calls{UniValue::VOBJ}, costs{UniValue::VOBJ};
        for(size_t i=0;i<256;++i) {
            if(opcodes[i]) ops.pushKV(std::to_string(i),opcodes[i]);
            if(function_calls[i]) calls.pushKV(std::to_string(i),function_calls[i]);
            if(function_varops[i]) costs.pushKV(std::to_string(i),function_varops[i]);
        }
        r.pushKV("opcodes",ops); r.pushKV("function_calls",calls); r.pushKV("function_body_varops_inclusive",costs);
        return r;
    }
};
inline thread_local GsrProfile gsr_profile;
struct GsrFunctionSample {
    uint8_t id;
    varops::Budget& budget;
    uint64_t before;
    GsrFunctionSample(uint8_t i,varops::Budget& b):id(i),budget(b),before(b.Remaining().value_or(0)) {
        if(gsr_profile.enabled) { ++gsr_profile.function_calls[id]; ++gsr_profile.invocations; }
    }
    ~GsrFunctionSample() {
        if(gsr_profile.enabled) gsr_profile.function_varops[id]+=before-budget.Remaining().value_or(0);
    }
};
#endif
