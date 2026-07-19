#!/usr/bin/env python3
"""
Module 01 pipeline: BV-BRC genome_id -> FASTA -> AMRFinderPlus -> structured features.

For each genome_id:
  1. Download assembled contigs from BV-BRC genome_sequence API, write gzipped FASTA
     (kept permanently in genomes/<id>.fna.gz).
  2. Decompress to a scratch .fna file.
  3. Run NCBI AMRFinderPlus (via the official `ncbi/amr` Docker image) with
     --organism Klebsiella_pneumoniae --plus, which adds organism-specific point-mutation
     detection on top of acquired-gene detection.
  4. Save the raw AMRFinderPlus TSV report (amrfinder_raw/<id>.tsv) and delete the scratch .fna.

Usage:
    python3 build_features.py <genome_ids.txt> <output_dir> [--workers N] [--limit N]
"""
import gzip
import json
import os
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

SEQ_API = "https://www.bv-brc.org/api/genome_sequence/"
ORGANISM = "Klebsiella_pneumoniae"


def fetch_genome_fasta(genome_id: str) -> str:
    query = f"eq(genome_id,{genome_id})&select(accession,description,sequence)&sort(+accession)&limit(2000)"
    url = SEQ_API + "?" + query
    req = urllib.request.Request(url, headers={"accept": "application/json"})
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode())
            if not data:
                raise ValueError("empty response")
            lines = []
            for contig in data:
                header = f">{contig['accession']} {contig.get('description', '')}".strip()
                seq = contig["sequence"]
                lines.append(header)
                for i in range(0, len(seq), 70):
                    lines.append(seq[i:i + 70])
            return "\n".join(lines) + "\n"
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{genome_id}: fetch failed after retries: {last_err}")


def process_one(genome_id: str, genomes_dir: str, scratch_dir: str, amr_dir: str) -> str:
    gz_path = os.path.join(genomes_dir, f"{genome_id}.fna.gz")
    tsv_path = os.path.join(amr_dir, f"{genome_id}.tsv")
    if os.path.exists(tsv_path):
        return "skip"

    if not os.path.exists(gz_path):
        fasta = fetch_genome_fasta(genome_id)
        with gzip.open(gz_path, "wt") as f:
            f.write(fasta)

    scratch_fna = os.path.join(scratch_dir, f"{genome_id}.fna")
    with gzip.open(gz_path, "rt") as f_in, open(scratch_fna, "w") as f_out:
        f_out.write(f_in.read())

    try:
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{scratch_dir}:/data",
            "ncbi/amr", "amrfinder",
            "-n", f"/data/{genome_id}.fna",
            "-O", ORGANISM, "--plus",
            "-o", f"/data/{genome_id}.out.tsv",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"amrfinder failed: {result.stderr[-500:]}")
        scratch_out = os.path.join(scratch_dir, f"{genome_id}.out.tsv")
        os.replace(scratch_out, tsv_path)
        return "ok"
    finally:
        if os.path.exists(scratch_fna):
            os.remove(scratch_fna)


def main():
    ids_file, out_dir = sys.argv[1], sys.argv[2]
    workers = 8
    limit = None
    if "--workers" in sys.argv:
        workers = int(sys.argv[sys.argv.index("--workers") + 1])
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    with open(ids_file) as f:
        genome_ids = [line.strip() for line in f if line.strip()]
    if limit:
        genome_ids = genome_ids[:limit]

    genomes_dir = os.path.join(out_dir, "genomes")
    scratch_dir = os.path.join(out_dir, "_scratch")
    amr_dir = os.path.join(out_dir, "amrfinder_raw")
    for d in (genomes_dir, scratch_dir, amr_dir):
        os.makedirs(d, exist_ok=True)

    done, failed = 0, []
    t0 = time.time()

    def work(gid):
        return gid, process_one(gid, genomes_dir, scratch_dir, amr_dir)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(work, gid): gid for gid in genome_ids}
        for fut in as_completed(futures):
            gid = futures[fut]
            try:
                _, status = fut.result()
            except Exception as e:
                status = f"FAIL: {e}"
                failed.append(gid)
            done += 1
            if done % 10 == 0 or done == len(genome_ids):
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(genome_ids) - done) / rate if rate > 0 else float("inf")
                print(f"[{done}/{len(genome_ids)}] elapsed={elapsed:.0f}s rate={rate:.2f}/s eta={eta:.0f}s last={gid}:{status}", flush=True)

    print(f"DONE. total={len(genome_ids)} failed={len(failed)}", flush=True)
    if failed:
        with open(os.path.join(out_dir, "_failed_amrfinder.txt"), "w") as f:
            f.write("\n".join(failed) + "\n")


if __name__ == "__main__":
    main()
