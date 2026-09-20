//! Native C measurement with the exact ABI in simplicity-sys 0.7.0 eval.h.
//! Its optional test wrapper omits minCost; do not call that wrapper.
use simplicity::ffi::{self, CElementsTxEnv};
use ffi::ffi::{c_size_t, c_uchar, UWORD, ubounded, sha256::CSha256Midstate};
use ffi::tests::ffi::{
    SimplicityErr,
    bitstream::{CBitstream, simplicity_closeBitstream},
    dag::{CDagNode, CCombinatorCounters, simplicity_fillWitnessData, simplicity_verifyNoDuplicateIdentityHashes},
    ty::CType,
    deserialize::simplicity_decodeMallocDag,
    elements::{simplicity_elements_decodeJet, simplicity_elements_mallocBoundVars},
    type_inference::simplicity_mallocTypeInference,
};
use std::{ptr, time::Instant};

extern "C" {
    #[link_name = "rustsimplicity_0_7_evalTCOExpression"]
    fn eval_expression(checks: c_uchar, output: *mut UWORD, input: *const UWORD,
        dag: *const CDagNode, types: *mut CType, len: c_size_t,
        min_cost: ubounded, budget: *const ubounded, env: *const CElementsTxEnv) -> SimplicityErr;
}

struct Allocation(*mut u8);
impl Drop for Allocation {
    fn drop(&mut self) { unsafe { ffi::alloc::rust_0_7_free(self.0); } }
}

pub fn measure(program: &[u8], witness: &[u8], env: &CElementsTxEnv, repeats: u64)
    -> Result<(Vec<u64>, Vec<u64>), String> {
    let mut execution = Vec::new();
    let mut validation = Vec::new();
    // Safety: DAG and type allocations live through evaluation. All decoding,
    // type inference, witness, uniqueness and 1->1 checks precede execution.
    // Types and the explicit minCost argument match the pinned C header.
    for _ in 0..repeats {
        let start = Instant::now();
        unsafe {
            let run = || -> Result<u64, SimplicityErr> {
                let mut stream = CBitstream::from(program);
                let mut wit = CBitstream::from(witness);
                let mut dag = ptr::null_mut();
                let mut census = CCombinatorCounters::default();
                let len = SimplicityErr::from_i32(simplicity_decodeMallocDag(
                    &mut dag, simplicity_elements_decodeJet, &mut census, &mut stream))? as usize;
                let _dag = Allocation(dag as *mut u8);
                if len == 0 || dag.is_null() { return Err(SimplicityErr::DataOutOfRange); }
                SimplicityErr::from_i32(simplicity_closeBitstream(&mut stream))?;
                let mut types = ptr::null_mut();
                simplicity_mallocTypeInference(&mut types, simplicity_elements_mallocBoundVars,
                    dag, len, &census).into_result()?;
                let _types = Allocation(types as *mut u8);
                if types.is_null() { return Err(SimplicityErr::Malloc); }
                simplicity_fillWitnessData(dag, types, len, &mut wit).into_result()?;
                SimplicityErr::from_i32(simplicity_closeBitstream(&mut wit))?;
                simplicity_verifyNoDuplicateIdentityHashes(&mut CSha256Midstate::default(), dag, types, len).into_result()?;
                if (*dag.add(len-1)).aux_types.types != [0, 0] {
                    return Err(SimplicityErr::TypeInferenceNotProgram);
                }
                let execute_start = Instant::now();
                // Zero disables the minimum-cost requirement; no transaction
                // budget is asserted in this standalone experiment.
                eval_expression(0xff, ptr::null_mut(), ptr::null(), dag, types,
                    len, 0, ptr::null(), env).into_result()?;
                Ok(execute_start.elapsed().as_nanos() as u64)
            };
            execution.push(run().map_err(|e| format!("C evaluator: {e:?}"))?);
        }
        validation.push(start.elapsed().as_nanos() as u64);
    }
    Ok((execution, validation))
}
