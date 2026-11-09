# AEGIS-UAV reproducibility pipeline.
#   make setup       install pinned dependencies (into the active Python environment)
#   make data        download COCO val2017 (+ COCO128 smoke-test set)
#   make test        unit, integration, and kernel-parity tests
#   make results     regenerate the COCO accuracy, codec, timing and system-study results (GPU recommended, ~1.5 h)
#   make generalization  detectors, bit widths, resolutions, aerial images, Monte Carlo (~5 h)
#   make validate    cross-check the simulator against ns-3 (needs NS3_DIR; see validation/README.md)
#   make validate-omnetpp  the same against OMNeT++/INET/Simu5G
#   make paper       tables, figures, and the PDF from the result files
#   make reproduce   clean-cache, data, test, results, generalization, paper (not validate or validate-omnetpp;
#                    the hardware runs, VisDrone fine-tuning and learned bottleneck are separate steps, see README)
PYTHON ?= python3
RESULTS := experiments/results

.PHONY: setup data test graph traces accuracy codecs pareto quant system results generalization scenarios validate validate-omnetpp tables figures paper reproduce clean-cache help

help:
	@sed -n '2,11p' Makefile

setup:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install -e . --no-deps

data:
	$(PYTHON) scripts/prepare_datasets.py

test:
	$(PYTHON) -m pytest -q

graph:
	$(PYTHON) core/inspect_graph.py

traces:
	$(PYTHON) -m simulation.trace_generator

accuracy: graph
	$(PYTHON) -m evaluation.evaluate_mAP

codecs: accuracy
	$(PYTHON) -m evaluation.benchmark_codecs

pareto: codecs
	$(PYTHON) -m evaluation.benchmark_split_pareto

quant: pareto
	$(PYTHON) -m evaluation.benchmark_quant_modes

system: pareto traces
	$(PYTHON) -m evaluation.benchmark_system

results: accuracy codecs pareto quant system

scenarios: pareto
	$(PYTHON) -m evaluation.gen_scenarios

generalization: codecs scenarios
	PYTHON=$(PYTHON) bash scripts/run_generalization.sh download
	PYTHON=$(PYTHON) bash scripts/run_generalization.sh gpu

validate:
	$(PYTHON) -m validation.run_channel_statistics
	$(PYTHON) -m validation.run_link_validation
	$(PYTHON) -m validation.run_stream_validation
	$(PYTHON) -m validation.run_relay_validation
	$(PYTHON) -m validation.run_calibrated_system
	$(PYTHON) -m validation.run_relay_forwarding

# needs OMNeT++/INET/Simu5G (OMNET_ENV) and ns-3 (NS3_DIR); see validation/README.md
validate-omnetpp:
	$(PYTHON) -m validation.run_omnetpp_validation
	$(PYTHON) -m validation.run_omnetpp_a2a
	$(PYTHON) -m validation.run_sharing_sensitivity

tables:
	$(PYTHON) -m evaluation.make_tables
	$(PYTHON) -m evaluation.make_generalization
	$(PYTHON) -m evaluation.make_validation
	$(PYTHON) -m evaluation.placement_model_check
	$(PYTHON) -m evaluation.make_hardware
	$(PYTHON) -m evaluation.make_learned

figures:
	$(PYTHON) -m evaluation.make_figures

paper: tables figures
	cd paper && bash build_paper.sh

reproduce: clean-cache data test results generalization paper

clean-cache:
	rm -rf experiments/cache
