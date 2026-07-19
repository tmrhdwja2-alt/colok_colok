from app.fasta import FastaValidationError, validate_fasta


def test_valid_fasta_quality():
    result = validate_fasta(b">contig-1\n" + b"ACGT" * 200)
    assert result.contigs == 1
    assert result.total_bases == 800
    assert result.gc_fraction == 0.5


def test_rejects_sequence_before_header():
    try:
        validate_fasta(b"ACGT" * 200)
    except FastaValidationError as exc:
        assert "before the first FASTA header" in str(exc)
    else:
        raise AssertionError("Expected validation to fail")

