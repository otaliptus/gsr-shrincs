#!/usr/bin/env python3
"""Build an observation-only source overlay; never edit the pinned submodule."""
from pathlib import Path
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'vendor/bitcoin'
TARGET=ROOT/'build/profile-source'

def replace_once(text,needle,replacement):
    if text.count(needle)!=1:raise RuntimeError(f'overlay source mismatch: {needle[:70]}')
    return text.replace(needle,replacement)

def write_changed(path,text):
    if not path.exists() or path.read_text()!=text:path.write_text(text)

def prepare():
    if not TARGET.exists():shutil.copytree(SOURCE,TARGET,ignore=shutil.ignore_patterns('.git','__pycache__'))
    write_changed(TARGET/'src/gsr_profile.hpp',(ROOT/'runner/profile.hpp').read_text())
    text=(SOURCE/'src/script/interpreter.cpp').read_text()
    text='#include <gsr_profile.hpp>\n'+text
    needle='    ValtypeStack& altstack{shared_altstack ? *shared_altstack : local_altstack};'
    observe='''
    const auto gsr_observe = [&]() {
        if (!gsr_profile.enabled) return;
        const uint64_t entries=stack.size()+altstack.size();
        const uint64_t bytes=stack.GetTotalSize()+altstack.GetTotalSize();
        gsr_profile.stack_entries=std::max(gsr_profile.stack_entries,entries);
        gsr_profile.stack_bytes=std::max(gsr_profile.stack_bytes,bytes);
        gsr_profile.total_entries=std::max(gsr_profile.total_entries,entries+function_state.definition_count);
        gsr_profile.total_bytes=std::max(gsr_profile.total_bytes,bytes+function_state.stored_body_bytes);
        gsr_profile.max_item=std::max<uint64_t>(gsr_profile.max_item,std::max(stack.GetMaxElementSize(),altstack.GetMaxElementSize()));
        gsr_profile.function_storage=std::max<uint64_t>(gsr_profile.function_storage,function_state.stored_body_bytes);
        gsr_profile.executed_bodies=std::max<uint64_t>(gsr_profile.executed_bodies,function_state.invoked_body_bytes);
    };
    gsr_observe();
'''
    text=replace_once(text,needle,needle+observe)
    needle='            const bool executes_opcode{fExec || (OP_IF <= opcode && opcode <= OP_ENDIF)};'
    text=replace_once(text,needle,needle+'''
            if (gsr_profile.enabled && executes_opcode) ++gsr_profile.opcodes[static_cast<uint8_t>(opcode)];
            if (gsr_profile.enabled && fExec && opcode == OP_SHA256 && stack.size()) {
                ++gsr_profile.sha_calls;
                gsr_profile.sha_compressions += (stack.back().size()+9+63)/64;
            }
''')
    needle='                    function_state.active[id] = true;'
    text=replace_once(text,needle,'                    GsrFunctionSample gsr_sample{id,varops_budget};\n'+needle)
    needle='            // Size limits\n            const size_t stack_entries{stack.size() + altstack.size()};'
    text=replace_once(text,needle,'            gsr_observe();\n'+needle)
    write_changed(TARGET/'src/script/interpreter.cpp',text)
    text=(SOURCE/'src/bitcoin-util.cpp').read_text()
    text='#include <gsr_profile.hpp>\n#include <consensus/validation.h>\n#include <policy/policy.h>\n#include <primitives/transaction.h>\n'+text
    needle='    argsman.AddCommand("evalscript", "Evaluate a standalone Tapscript v2 script from a JSON request on standard input");'
    text=replace_once(text,needle,needle+'\n    argsman.AddCommand("measuretx", "Measure recorded transaction Script validation");')
    needle='    const std::optional<bool> op_success{\n        CheckTapscriptOpSuccess(script, SCRIPT_VERIFY_NONE, SigVersion::TAPSCRIPT_V2, &error)};'
    text=replace_once(text,needle,'''    gsr_profile={};
    if(request.exists("profile")) gsr_profile.enabled=request["profile"].get_bool();
    const auto gsr_start=std::chrono::steady_clock::now();
'''+needle)
    needle='    UniValue result{UniValue::VOBJ};\n    result.pushKV("protocol", 1);'
    text=replace_once(text,needle,'''    const uint64_t gsr_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-gsr_start).count();
'''+needle+'\n    result.pushKV("profile", gsr_profile.Json(gsr_ns));')
    text=replace_once(text,'MAIN_FUNCTION\n{',(ROOT/'runner/measuretx.inc').read_text()+'\nMAIN_FUNCTION\n{')
    needle='        } else if (cmd->command == "evalscript") {'
    text=replace_once(text,needle,'''        } else if (cmd->command == "measuretx") {
            ret = MeasureTransactionCommand(cmd->args, strPrint);
'''+needle)
    write_changed(TARGET/'src/bitcoin-util.cpp',text)

def main():
    prepare()
    configure=['cmake','-S',str(TARGET),'-B',str(ROOT/'build/profile'),'-G','Ninja',
       '-DCMAKE_BUILD_TYPE=Release','-DENABLE_IPC=OFF','-DENABLE_WALLET=OFF',
       '-DBUILD_GUI=OFF','-DWITH_CCACHE=OFF','-DBUILD_TESTS=OFF','-DBUILD_DAEMON=OFF',
       '-DBUILD_CLI=OFF','-DBUILD_TX=OFF','-DBUILD_UTIL=ON']
    local=ROOT/'build/deps/usr'
    if local.exists():configure+=['-DCMAKE_PREFIX_PATH='+str(local)]
    subprocess.run(configure,check=True)
    subprocess.run(['cmake','--build',str(ROOT/'build/profile'),'--target','bitcoin-util','-j',sys.argv[1] if len(sys.argv)>1 else '4'],check=True)
if __name__=='__main__':main()
