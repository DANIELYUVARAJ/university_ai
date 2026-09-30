"""
University DataShield - Phase 11 Performance & Concurrency Benchmark
Measures:
1. Concurrent synthetic pipelines (1, 5, 10, 25 concurrent pipelines)
2. Scalability on large synthetic datasets (1K, 10K, 50K rows)
All processing uses synthetic data with zero real PII retention.
"""

import sys
import time
import asyncio
import statistics
from pathlib import Path

# Add backend to path
REPO_ROOT = Path(__file__).resolve().parent.parent
backend_path = REPO_ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from pipeline.schemas import PipelineValidateRequest, DatasetFormat
from pipeline.pipeline_service import PipelineService


def generate_synthetic_csv(row_count: int) -> str:
    """Generate memory-efficient synthetic CSV dataset without PII retention."""
    lines = ["student_id,full_name,email,gpa,department,scholarship_amount"]
    for i in range(1, row_count + 1):
        lines.append(f"U{10000000 + i},Student {i},student{i}@univ.edu,{3.0 + (i % 100) / 100.0},Dept_{i % 5},{1000 + (i % 10) * 500}")
    return "\n".join(lines) + "\n"


async def benchmark_single_pipeline(payload: PipelineValidateRequest) -> dict:
    t0 = time.perf_counter()
    resp = await PipelineService.validate_pipeline(payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "pipeline_id": resp.pipeline_id,
        "decision": resp.decision,
        "elapsed_ms": elapsed_ms,
        "sensitive_fields_count": len(resp.sensitive_fields),
        "violations_count": len(resp.policy_violations),
    }


async def run_concurrency_benchmark(concurrency_levels=(1, 5, 10, 25), rows_per_dataset=100):
    print("=" * 68)
    print(" PHASE 11 CONCURRENT PIPELINE EXECUTION BENCHMARK")
    print("=" * 68)
    csv_content = generate_synthetic_csv(rows_per_dataset)

    results = {}
    for conc in concurrency_levels:
        requests = [
            PipelineValidateRequest(
                dataset_name=f"concurrent_test_dataset_{idx}",
                raw_content=csv_content,
                format=DatasetFormat.CSV,
                role="DATA_ENGINEER",
            )
            for idx in range(conc)
        ]

        t_start = time.perf_counter()
        tasks = [benchmark_single_pipeline(req) for req in requests]
        outcomes = await asyncio.gather(*tasks)
        total_time_s = time.perf_counter() - t_start

        latencies = [o["elapsed_ms"] for o in outcomes]
        throughput = conc / total_time_s if total_time_s > 0 else 0
        avg_lat = statistics.mean(latencies)
        max_lat = max(latencies)
        min_lat = min(latencies)
        blocked_count = sum(1 for o in outcomes if o["decision"] == "BLOCK")

        results[conc] = {
            "pipelines": conc,
            "total_time_s": round(total_time_s, 3),
            "throughput_pipelines_per_sec": round(throughput, 2),
            "avg_latency_ms": round(avg_lat, 2),
            "min_latency_ms": round(min_lat, 2),
            "max_latency_ms": round(max_lat, 2),
            "blocked_count": blocked_count,
            "allowed_count": conc - blocked_count,
        }

        print(f" Concurrency: {conc:2d} pipelines | Total: {total_time_s:5.3f}s | "
              f"Throughput: {throughput:6.2f} pipe/s | Avg Lat: {avg_lat:6.2f}ms | Max Lat: {max_lat:6.2f}ms")

    return results


async def run_dataset_size_benchmark(sizes=(1000, 10000, 50000)):
    print("\n" + "=" * 68)
    print(" PHASE 11 LARGE SYNTHETIC DATASET BENCHMARK")
    print("=" * 68)

    results = {}
    for size in sizes:
        print(f" Generating {size:,} synthetic rows...")
        t_gen = time.perf_counter()
        csv_content = generate_synthetic_csv(size)
        gen_ms = (time.perf_counter() - t_gen) * 1000.0

        req = PipelineValidateRequest(
            dataset_name=f"synthetic_large_{size}_rows",
            raw_content=csv_content,
            format=DatasetFormat.CSV,
            role="DATA_ENGINEER",
        )

        t_run = time.perf_counter()
        resp = await PipelineService.validate_pipeline(req)
        run_ms = (time.perf_counter() - t_run) * 1000.0

        results[size] = {
            "rows": size,
            "generation_ms": round(gen_ms, 2),
            "pipeline_validation_ms": round(run_ms, 2),
            "decision": resp.decision,
            "sensitive_fields_found": len(resp.sensitive_fields),
            "violations_found": len(resp.policy_violations),
        }

        print(f" Rows: {size:6,d} | Gate Decision: {resp.decision:5s} | "
              f"Sensitive Fields: {len(resp.sensitive_fields)} | Validation: {run_ms:7.2f} ms")

    return results


async def main():
    conc_results = await run_concurrency_benchmark()
    size_results = await run_dataset_size_benchmark()

    print("\n" + "=" * 68)
    print(" BENCHMARK COMPLETED SUCCESSFULLY")
    print("=" * 68)


if __name__ == "__main__":
    asyncio.run(main())
