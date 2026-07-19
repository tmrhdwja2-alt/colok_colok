# License & Attribution

## Data sources

**Genome sequences, quality metrics, and antimicrobial susceptibility labels**: retrieved from
**BV-BRC** (Bacterial and Viral Bioinformatics Resource Center), https://www.bv-brc.org, via its
public REST Data API (`https://www.bv-brc.org/api/`).

**AMR gene/mutation annotation**: generated locally in this pipeline using **NCBI AMRFinderPlus**
(https://github.com/ncbi/amr), run via the official `ncbi/amr` Docker image. AMRFinderPlus and its
reference database are explicitly public-domain and unrestricted (stated in the challenge brief
and in the tool's own documentation).

## Required citation (BV-BRC)

Per https://www.bv-brc.org/citation:

> Olson RD, Assaf R, Brettin T, et al. "Introducing the Bacterial and Viral Bioinformatics
> Resource Center (BV-BRC): a resource combining PATRIC, IRD and ViPR." *Nucleic Acids Research*,
> 2022 Nov 9:gkac1003.

Short form: The Bacterial and Viral Bioinformatics Resource Center (BV-BRC), https://www.bv-brc.org/

## Funding acknowledgment

BV-BRC is funded in whole or in part with federal funds from the National Institute of Allergy
and Infectious Diseases (NIAID), National Institutes of Health, Department of Health and Human
Services, under Grant No. U24AI183849 to the University of Chicago.

## AMRFinderPlus citation

Feldgarden M, et al. "AMRFinderPlus and the Reference Gene Catalog facilitate examination of the
genomic links among antimicrobial resistance, stress response, and virulence." *Scientific
Reports*, 2021.

## Underlying data provenance

Individual genome records were originally deposited to GenBank/SRA by many independent research
groups and public-health laboratories worldwide. BV-BRC aggregates, quality-checks, and annotates
these public submissions but does not itself generate the genomes or independently re-verify
susceptibility test results. Each genome's `bioproject_accession`, `biosample_accession`, and
`sra_accession` (where available) are recorded in `genome_metadata_final.csv`, and each AMR label
row in `amr_labels_final.csv` records `laboratory_typing_methods_seen`, `testing_standards_seen`,
and `pmids` where available, so provenance can be traced back to the original depositor/publication.

## Terms of use note

BV-BRC's citation page does not publish a separate formal data license (e.g. CC0/CC-BY) beyond the
citation request above; data are described throughout BV-BRC's documentation as "freely available"
to all users.

## Scope disclaimer (from the challenge brief, `주제6.pdf` appendix)

"Research prototype. Predictions based on historical bacterial genome data do not prove that the
system is safe, accurate enough, approved, or suitable for real healthcare decisions. Every
antibiotic-response report must be confirmed with standard laboratory testing."
