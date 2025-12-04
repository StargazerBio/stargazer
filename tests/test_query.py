"""
Unit tests for query generation utilities.
"""
from stargazer.utils.query import generate_query_combinations


class TestGenerateQueryCombinations:
    """Test cases for generate_query_combinations function."""

    def test_scalar_filters_only(self):
        """Test with only scalar-valued filters."""
        base = {"type": "reference"}
        filters = {"build": "GRCh38", "format": "fasta"}

        result = generate_query_combinations(base, filters)

        assert len(result) == 1
        assert result[0] == {
            "type": "reference",
            "build": "GRCh38",
            "format": "fasta",
        }

    def test_single_list_filter(self):
        """Test with one list-valued filter."""
        base = {"type": "reference"}
        filters = {"build": "GRCh38", "tool": ["fasta", "bwa", "faidx"]}

        result = generate_query_combinations(base, filters)

        assert len(result) == 3
        assert result[0] == {"type": "reference", "build": "GRCh38", "tool": "fasta"}
        assert result[1] == {"type": "reference", "build": "GRCh38", "tool": "bwa"}
        assert result[2] == {"type": "reference", "build": "GRCh38", "tool": "faidx"}

    def test_multiple_list_filters_cartesian_product(self):
        """Test cartesian product with multiple list-valued filters."""
        base = {"type": "reference"}
        filters = {
            "build": ["GRCh38", "GRCh37"],
            "tool": ["fasta", "bwa"],
        }

        result = generate_query_combinations(base, filters)

        # Should generate 2 x 2 = 4 combinations
        assert len(result) == 4

        # Verify all combinations are present
        expected = [
            {"type": "reference", "build": "GRCh38", "tool": "fasta"},
            {"type": "reference", "build": "GRCh38", "tool": "bwa"},
            {"type": "reference", "build": "GRCh37", "tool": "fasta"},
            {"type": "reference", "build": "GRCh37", "tool": "bwa"},
        ]

        for expected_query in expected:
            assert expected_query in result

    def test_three_dimensional_cartesian_product(self):
        """Test cartesian product with three list-valued filters."""
        base = {"type": "reference"}
        filters = {
            "build": ["GRCh38", "GRCh37"],
            "tool": ["fasta", "bwa"],
            "organism": ["human", "mouse"],
        }

        result = generate_query_combinations(base, filters)

        # Should generate 2 x 2 x 2 = 8 combinations
        assert len(result) == 8

        # Verify a sample of combinations
        assert {
            "type": "reference",
            "build": "GRCh38",
            "tool": "fasta",
            "organism": "human",
        } in result
        assert {
            "type": "reference",
            "build": "GRCh37",
            "tool": "bwa",
            "organism": "mouse",
        } in result

    def test_mixed_scalar_and_list_filters(self):
        """Test with both scalar and list-valued filters."""
        base = {"type": "reference"}
        filters = {
            "build": "GRCh38",  # scalar
            "format": "fasta",  # scalar
            "tool": ["indexer", "aligner"],  # list
        }

        result = generate_query_combinations(base, filters)

        assert len(result) == 2
        assert result[0] == {
            "type": "reference",
            "build": "GRCh38",
            "format": "fasta",
            "tool": "indexer",
        }
        assert result[1] == {
            "type": "reference",
            "build": "GRCh38",
            "format": "fasta",
            "tool": "aligner",
        }

    def test_empty_filters(self):
        """Test with no filters."""
        base = {"type": "reference"}
        filters = {}

        result = generate_query_combinations(base, filters)

        assert len(result) == 1
        assert result[0] == {"type": "reference"}

    def test_empty_base_query(self):
        """Test with empty base query."""
        base = {}
        filters = {"tool": ["fasta", "bwa"]}

        result = generate_query_combinations(base, filters)

        assert len(result) == 2
        assert result[0] == {"tool": "fasta"}
        assert result[1] == {"tool": "bwa"}

    def test_single_element_list_filter(self):
        """Test list filter with only one element."""
        base = {"type": "reference"}
        filters = {"build": "GRCh38", "tool": ["fasta"]}

        result = generate_query_combinations(base, filters)

        assert len(result) == 1
        assert result[0] == {"type": "reference", "build": "GRCh38", "tool": "fasta"}

    def test_preserves_base_query_values(self):
        """Test that base query values are preserved in all combinations."""
        base = {"type": "reference", "version": "1.0"}
        filters = {"tool": ["fasta", "bwa"]}

        result = generate_query_combinations(base, filters)

        assert len(result) == 2
        for query in result:
            assert query["type"] == "reference"
            assert query["version"] == "1.0"
