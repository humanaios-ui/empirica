"""
Unit tests for orphan_connectivity_validator module.

Run with: python -m pytest tests/test_orphan_connectivity.py -v
"""

import pytest
from empirica.cli.validators.orphan_connectivity import (
    validate_artifact_connectivity,
    validate_batch_artifacts,
    ConnectivityValidationError,
    ConnectivityValidationResult,
)


class TestValidateArtifactConnectivity:
    """Test cases for single artifact validation."""
    
    def test_valid_with_edges(self):
        """Artifact with edges is valid."""
        result = validate_artifact_connectivity(
            artifact_type='finding',
            claim_text='Test claim',
            edge_targets=['uuid-1', 'uuid-2'],
            enforce=False
        )
        assert result.valid is True
        assert result.edge_count == 2
    
    def test_valid_with_single_edge(self):
        """Artifact with single edge is valid."""
        result = validate_artifact_connectivity(
            artifact_type='finding',
            claim_text='Test claim',
            edge_targets=['uuid-1'],
            enforce=False
        )
        assert result.valid is True
        assert result.edge_count == 1
    
    def test_valid_with_reason_no_edges(self):
        """Artifact with reason_no_edges is valid."""
        result = validate_artifact_connectivity(
            artifact_type='finding',
            claim_text='Test claim',
            edge_targets=None,
            reason_no_edges='First artifact in investigation',
            enforce=False
        )
        assert result.valid is True
        assert result.has_reason_no_edges is True
    
    def test_invalid_no_edges_no_reason(self):
        """Artifact with no edges and no reason is invalid."""
        result = validate_artifact_connectivity(
            artifact_type='finding',
            claim_text='Test claim',
            edge_targets=None,
            reason_no_edges=None,
            enforce=False
        )
        assert result.valid is False
        assert result.edge_count == 0
    
    def test_invalid_empty_edge_list(self):
        """Artifact with empty edge list and no reason is invalid."""
        result = validate_artifact_connectivity(
            artifact_type='finding',
            claim_text='Test claim',
            edge_targets=[],
            reason_no_edges=None,
            enforce=False
        )
        assert result.valid is False
    
    def test_enforce_raises_on_invalid(self):
        """With enforce=True, raises error on invalid artifact."""
        with pytest.raises(ConnectivityValidationError):
            validate_artifact_connectivity(
                artifact_type='finding',
                claim_text='Test claim',
                edge_targets=None,
                reason_no_edges=None,
                enforce=True
            )
    
    def test_enforce_no_raise_on_valid(self):
        """With enforce=True, no error on valid artifact."""
        result = validate_artifact_connectivity(
            artifact_type='finding',
            claim_text='Test claim',
            edge_targets=['uuid-1'],
            enforce=True
        )
        assert result.valid is True


class TestValidateBatchArtifacts:
    """Test cases for batch validation."""
    
    def test_batch_all_valid(self):
        """Batch with all valid artifacts."""
        artifacts = [
            {
                'artifact_type': 'finding',
                'claim_text': 'Claim 1',
                'edge_targets': ['uuid-1'],
            },
            {
                'artifact_type': 'unknown',
                'claim_text': 'Claim 2',
                'reason_no_edges': 'First question',
            },
        ]
        result = validate_batch_artifacts(artifacts, enforce=False)
        assert result['valid_count'] == 2
        assert result['invalid_count'] == 0
        assert len(result['failures']) == 0
    
    def test_batch_mixed(self):
        """Batch with mix of valid and invalid artifacts."""
        artifacts = [
            {
                'artifact_type': 'finding',
                'claim_text': 'Valid finding',
                'edge_targets': ['uuid-1'],
            },
            {
                'artifact_type': 'finding',
                'claim_text': 'Invalid finding',
                'edge_targets': None,
                'reason_no_edges': None,
            },
        ]
        result = validate_batch_artifacts(artifacts, enforce=False)
        assert result['valid_count'] == 1
        assert result['invalid_count'] == 1
        assert len(result['failures']) == 1


class TestConnectivityValidationResult:
    """Test cases for result object."""
    
    def test_result_attributes(self):
        """Result has all expected attributes."""
        result = ConnectivityValidationResult(
            valid=True,
            message='Test message',
            artifact_id='test-id',
            edge_count=2,
            has_reason_no_edges=False
        )
        assert result.valid is True
        assert result.artifact_id == 'test-id'
        assert result.edge_count == 2


class TestLogVerbEnforcement:
    """The *-log handler helper: warn by default, reject when EMPIRICA_ORPHAN_ENFORCE=1."""

    @staticmethod
    def _args(edges=None, related=None, reason=None, evidence=None):
        from types import SimpleNamespace

        return SimpleNamespace(
            edges_raw=edges or [],
            related_to_ids=related or [],
            evidence_from_ids=evidence or [],
            reason_no_edges=reason,
        )

    def test_warns_without_edges_and_does_not_exit(self, monkeypatch, capsys):
        from empirica.cli.command_handlers.artifact_log_commands import _enforce_orphan_connectivity

        monkeypatch.delenv("EMPIRICA_ORPHAN_ENFORCE", raising=False)
        _enforce_orphan_connectivity(self._args(), "finding")
        assert "finding-log" in capsys.readouterr().err

    def test_enforce_rejects_without_edges(self, monkeypatch):
        from empirica.cli.command_handlers.artifact_log_commands import _enforce_orphan_connectivity

        monkeypatch.setenv("EMPIRICA_ORPHAN_ENFORCE", "1")
        with pytest.raises(SystemExit) as exc:
            _enforce_orphan_connectivity(self._args(), "unknown")
        assert exc.value.code == 1

    def test_enforce_passes_with_reason(self, monkeypatch, capsys):
        from empirica.cli.command_handlers.artifact_log_commands import _enforce_orphan_connectivity

        monkeypatch.setenv("EMPIRICA_ORPHAN_ENFORCE", "1")
        _enforce_orphan_connectivity(self._args(reason="first artifact"), "finding")
        assert capsys.readouterr().err == ""

    def test_enforce_passes_with_related_to(self, monkeypatch, capsys):
        from empirica.cli.command_handlers.artifact_log_commands import _enforce_orphan_connectivity

        monkeypatch.setenv("EMPIRICA_ORPHAN_ENFORCE", "1")
        _enforce_orphan_connectivity(self._args(related=["abc12345"]), "mistake")
        assert capsys.readouterr().err == ""

    def test_decision_counts_evidence_from_as_edge(self, monkeypatch, capsys):
        from empirica.cli.command_handlers.artifact_log_commands import _enforce_orphan_connectivity

        monkeypatch.setenv("EMPIRICA_ORPHAN_ENFORCE", "1")
        _enforce_orphan_connectivity(self._args(evidence=["f00dcafe"]), "decision", evidence_relation="evidence")
        assert capsys.readouterr().err == ""

    def test_reason_flag_parses_on_finding_log(self):
        import argparse

        from empirica.cli.parsers.checkpoint_parsers import _add_edge_flags

        p = argparse.ArgumentParser()
        _add_edge_flags(p)
        ns = p.parse_args(["--reason-no-edges", "why"])
        assert ns.reason_no_edges == "why"


class TestLogArtifactsBatchOrphans:
    """Orphan policy on the log-artifacts graph path (CLI and daemon share it)."""

    def test_connected_node_is_not_orphan(self):
        from empirica.cli.command_handlers.graph_commands import _orphan_node_refs

        graph = {
            "nodes": [{"ref": "f1", "type": "finding"}, {"ref": "u1", "type": "unknown"}],
            "edges": [{"from": "u1", "to": "f1", "relation": "raised_by"}],
        }
        assert _orphan_node_refs(graph) == []

    def test_isolated_node_is_orphan(self):
        from empirica.cli.command_handlers.graph_commands import _orphan_node_refs

        graph = {
            "nodes": [{"ref": "f1", "type": "finding"}, {"ref": "f2", "type": "finding"}],
            "edges": [{"from": "f1", "to": "f2", "relation": "related"}],
        }
        assert _orphan_node_refs(graph) == []
        graph["nodes"].append({"ref": "f3", "type": "finding"})
        assert _orphan_node_refs(graph) == ["f3"]

    def test_reason_no_edges_exempts_node(self):
        from empirica.cli.command_handlers.graph_commands import _orphan_node_refs

        graph = {"nodes": [{"ref": "f1", "type": "finding", "data": {"reason_no_edges": "standalone"}}]}
        assert _orphan_node_refs(graph) == []

    def test_enforce_rejects_batch_before_write(self, monkeypatch):
        from empirica.cli.command_handlers.graph_commands import log_artifacts_graph

        monkeypatch.setenv("EMPIRICA_ORPHAN_ENFORCE", "1")
        graph = {"nodes": [{"ref": "f1", "type": "finding"}]}
        result = log_artifacts_graph(graph)
        assert result["ok"] is False
        assert result["nodes_created"] == 0
        assert "f1" in result["errors"][0]

    def test_warn_mode_does_not_reject(self, monkeypatch, capsys):
        from empirica.cli.command_handlers import graph_commands

        monkeypatch.delenv("EMPIRICA_ORPHAN_ENFORCE", raising=False)
        # Stop before any DB work: the warning is printed first, then the write path runs.
        monkeypatch.setattr(graph_commands, "_orphan_node_refs", lambda g: ["f1"])

        class _Stop(Exception):
            pass

        def _boom(*a, **k):
            raise _Stop

        monkeypatch.setattr("empirica.data.session_database.SessionDatabase", _boom)
        with pytest.raises(_Stop):
            graph_commands.log_artifacts_graph({"nodes": [{"ref": "f1", "type": "finding"}]})
        assert "no edge" in capsys.readouterr().err
