ROOT  := $(realpath ..)
BUILD := $(ROOT)/sim/build

RTL   := $(ROOT)/rtl
TB    := $(ROOT)/sim/rtl/tb

IVERILOG := iverilog
VVP      := vvp

# -----------------------------------------------------------------------------
# Source lists
# -----------------------------------------------------------------------------
RTL_TRANS_N43_CORE := \
	$(RTL)/transposed_form/n43/fir_n43.v

RTL_TRANS_N43_TOP := \
	$(RTL)/transposed_form/decimator_m2_phase0.v \
	$(RTL_TRANS_N43_CORE) \
	$(RTL)/transposed_form/n43/fir_decimator_n43.v

RTL_TRANS_N43_AXIS := \
	$(RTL_TRANS_N43_TOP) \
	$(RTL)/transposed_form/n43/fir_decimator_n43_axis.v

RTL_DIRECT_N5_CORE := \
	$(RTL)/direct_form/bringup_n5/fir_direct_n5.v

RTL_DIRECT_N5_TOP := \
	$(RTL)/direct_form/decimator_m2_phase0.v \
	$(RTL_DIRECT_N5_CORE) \
	$(RTL)/direct_form/bringup_n5/fir_decimator_direct_n5_top.v

# -----------------------------------------------------------------------------
# Compiled targets (all output to sim/build/)
# -----------------------------------------------------------------------------
BINS_N43 := \
	$(BUILD)/tb_fir_n43.out \
	$(BUILD)/tb_fir_decimator_n43.out \
	$(BUILD)/tb_fir_decimator_n43_axis.out

BINS_LEGACY_N5 := \
	$(BUILD)/tb_fir_direct_n5.out \
	$(BUILD)/tb_fir_decimator_direct_n5_top.out

.PHONY: all run_all run_legacy_n5 clean

all: $(BINS_N43)

run_all: all
	@for bin in $(BINS_N43); do \
		echo "=== $$(basename $$bin) ==="; \
		cd $(ROOT) && $(VVP) $$bin; \
	done

run_legacy_n5: $(BINS_LEGACY_N5)
	@for bin in $(BINS_LEGACY_N5); do \
		echo "=== $$(basename $$bin) ==="; \
		cd $(ROOT) && $(VVP) $$bin; \
	done

clean:
	rm -rf $(BUILD)

$(BUILD):
	mkdir -p $@

# -----------------------------------------------------------------------------
# Transposed form N=43
# -----------------------------------------------------------------------------
$(BUILD)/tb_fir_n43.out: \
	$(TB)/transposed_form/tb_fir_n43.sv \
	$(RTL_TRANS_N43_CORE) | $(BUILD)
	$(IVERILOG) -g2012 -o $@ $^

$(BUILD)/tb_fir_decimator_n43.out: \
	$(TB)/transposed_form/tb_fir_decimator_n43.sv \
	$(RTL_TRANS_N43_TOP) | $(BUILD)
	$(IVERILOG) -g2012 -o $@ $^

$(BUILD)/tb_fir_decimator_n43_axis.out: \
	$(TB)/transposed_form/tb_fir_decimator_n43_axis.sv \
	$(RTL_TRANS_N43_AXIS) | $(BUILD)
	$(IVERILOG) -g2012 -o $@ $^

# -----------------------------------------------------------------------------
# Direct form N=5 (bringup)
# -----------------------------------------------------------------------------
$(BUILD)/tb_fir_direct_n5.out: \
	$(TB)/direct_form/tb_fir_direct_n5.v \
	$(RTL_DIRECT_N5_CORE) | $(BUILD)
	$(IVERILOG) -g2012 -o $@ $^

$(BUILD)/tb_fir_decimator_direct_n5_top.out: \
	$(TB)/direct_form/tb_fir_decimator_direct_n5_top.v \
	$(RTL_DIRECT_N5_TOP) | $(BUILD)
	$(IVERILOG) -g2012 -o $@ $^
