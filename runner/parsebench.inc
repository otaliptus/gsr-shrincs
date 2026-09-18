// Isolated parser benchmark over the recorded valid-program schedule.
// This command does not execute Script or change consensus accounting.
static int ParseBenchCommand(const std::vector<std::string>& args, std::string& strPrint)
{
    if (!args.empty()) throw std::runtime_error("parsebench takes stdin JSON only");
    const std::string input{std::istreambuf_iterator<char>{std::cin}, std::istreambuf_iterator<char>()};
    UniValue request;
    if (!request.read(input) || !request.isObject()) throw std::runtime_error("bad request");
    const uint64_t passes = RequiredEvalScriptField(request, "passes").getInt<uint64_t>();
    const bool copy_data = RequiredEvalScriptField(request, "copy_data").get_bool();
    if (!passes || passes > 64) throw std::runtime_error("passes outside laboratory bound");
    std::vector<std::pair<CScript, uint64_t>> schedule;
    uint64_t bytes_per_pass{0};
    for (const auto& item : RequiredEvalScriptField(request, "schedule").getValues()) {
        const auto code = ParseEvalScriptHex(RequiredEvalScriptField(item, "script"), "script");
        const uint64_t calls = RequiredEvalScriptField(item, "calls").getInt<uint64_t>();
        if (!calls || calls > 4096 || code.size() > 4'000'000) throw std::runtime_error("schedule outside laboratory bound");
        bytes_per_pass += code.size() * calls;
        if (bytes_per_pass > 16'000'000) throw std::runtime_error("schedule too large");
        schedule.emplace_back(CScript{code.begin(), code.end()}, calls);
    }
    uint64_t instructions{0}, payload_bytes{0}, checksum{0};
    const auto start = std::chrono::steady_clock::now();
    for (uint64_t pass = 0; pass < passes; ++pass) {
        for (const auto& [script, calls] : schedule) {
            for (uint64_t call = 0; call < calls; ++call) {
                auto pc = script.begin();
                valtype payload;
                while (pc != script.end()) {
                    opcodetype opcode;
                    const bool valid = copy_data ? script.GetOp(pc, opcode, payload) : script.GetOp(pc, opcode);
                    if (!valid) throw std::runtime_error("malformed recorded program");
                    ++instructions;
                    checksum += static_cast<uint8_t>(opcode);
                    if (copy_data) payload_bytes += payload.size();
                }
            }
        }
    }
    const uint64_t ns = std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now() - start).count();
    UniValue result{UniValue::VOBJ};
    result.pushKV("protocol", 1); result.pushKV("context", "isolated-parser-benchmark");
    result.pushKV("passes", passes); result.pushKV("copy_data", copy_data);
    result.pushKV("bytes_per_pass", bytes_per_pass); result.pushKV("instructions", instructions);
    result.pushKV("payload_bytes", payload_bytes); result.pushKV("checksum", checksum);
    result.pushKV("elapsed_ns", ns); strPrint = result.write(); return EXIT_SUCCESS;
}
