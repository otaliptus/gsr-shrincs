# GSR SHRINCS verifier research

Implement and measure the pinned SHRINCS verification algorithm in the experimental GSR Bitcoin Script environment, then bind it to a regtest transaction.

**Status:** planning and source checkout; CMake configuration succeeded on the originating machine. No verifier implementation, compiled evaluator, executed tests, or performance results yet.

Start with [HANDOFF.md](HANDOFF.md). It records the full scope, current state, source pins, milestones, technical findings, and commands for continuing on another machine. [PLAN.md](PLAN.md) contains the detailed research plan, comparisons with BitVM, and other possible GSR applications.

```sh
git clone --recurse-submodules https://github.com/otaliptus/gsr-shrincs.git
cd gsr-shrincs
```

This repository is private. Authenticate to GitHub with an account that has access. The two upstream submodules are public and pinned to exact commits.

This is experimental verification research, not a production signer, wallet, or claim of Bitcoin activation. Use public test seeds and local regtest only.
