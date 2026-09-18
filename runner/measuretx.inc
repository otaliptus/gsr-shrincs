// Offline Script measurement. Prevouts come from recorded regtest UTXOs.
// This adapter is NOT node validation or a source of authenticated UTXOs.
static int MeasureTransactionCommand(const std::vector<std::string>& args, std::string& strPrint)
{
    if (!args.empty()) throw std::runtime_error("measuretx takes stdin JSON only");
    const std::string input{std::istreambuf_iterator<char>{std::cin}, std::istreambuf_iterator<char>()};
    UniValue request;
    if (!request.read(input) || !request.isObject()) throw std::runtime_error("bad request");
    CMutableTransaction tx;
    if (!DecodeHexTx(tx, RequiredEvalScriptField(request,"transaction").get_str())) throw std::runtime_error("bad transaction");
    std::vector<CTxOut> spent;
    const auto spent_values=RequiredEvalScriptField(request,"spent_outputs").getValues();
    for(const auto& item:spent_values) {
        const auto bytes=ParseEvalScriptHex(item,"spent_output");
        DataStream stream{bytes};
        CTxOut output; stream >> output;
        if(!stream.empty()) throw std::runtime_error("trailing spent-output bytes");
        spent.push_back(output);
    }
    if(spent.size()!=tx.vin.size() || tx.vin.empty()) throw std::runtime_error("prevout count mismatch");
    PrecomputedTransactionData precomputed;
    precomputed.Init(tx,std::move(spent),true);
    const uint64_t weight=GetTransactionWeight(CTransaction{tx});
    const uint64_t allowance=varops::TxBudget(weight);
    varops::Budget budget{allowance};
    gsr_profile={};
    if(request.exists("profile")) gsr_profile.enabled=request["profile"].get_bool();
    const auto start=std::chrono::steady_clock::now();
    bool success=true;
    ScriptError error{SCRIPT_ERR_UNKNOWN_ERROR};
    UniValue inputs{UniValue::VARR};
    for(size_t i=0;i<tx.vin.size();++i) {
        const uint64_t before=budget.Remaining().value();
        MutableTransactionSignatureChecker checker{&tx,static_cast<unsigned int>(i),precomputed.m_spent_outputs[i].nValue,precomputed,MissingDataBehavior::FAIL};
        const bool ok=VerifyScript(tx.vin[i].scriptSig,precomputed.m_spent_outputs[i].scriptPubKey,&tx.vin[i].scriptWitness,
            STANDARD_SCRIPT_VERIFY_FLAGS | SCRIPT_VERIFY_SCRIPT_RESTORATION,checker,&error,budget);
        UniValue row{UniValue::VOBJ}; row.pushKV("input",i); row.pushKV("success",ok);
        row.pushKV("consumed",before-budget.Remaining().value());
        if(!ok) row.pushKV("error",ScriptErrorString(error));
        inputs.push_back(row);
        if(!ok) {success=false;break;}
    }
    const uint64_t ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-start).count();
    UniValue result{UniValue::VOBJ}; result.pushKV("protocol",1); result.pushKV("context","offline-transaction-script-check");
    result.pushKV("success",success); result.pushKV("weight",weight); result.pushKV("varops_allowed",allowance);
    result.pushKV("varops_consumed",allowance-budget.Remaining().value()); result.pushKV("inputs",inputs);
    result.pushKV("profile",gsr_profile.Json(ns)); strPrint=result.write(); return EXIT_SUCCESS;
}
