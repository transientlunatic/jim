# Jim Asimov Interface

This directory contains the asimov pipeline interface for jim, allowing automated gravitational-wave parameter estimation workflows.

## Compatibility

The jim asimov interface is compatible with:
- **asimov master branch** (v0.6.x and earlier)
- **asimov v0.7-preview** and later versions

The interface automatically detects the asimov version and provides appropriate compatibility features.

## Installation

To use the asimov interface, install jim with the asimov extra:

```bash
pip install jimgw[asimov]
```

## Features

The jim asimov interface supports:

- **External PSDs**: Use PSDs from previous analyses instead of estimating from data
- **External Data Files**: Use frame files or data from previous analyses
- **Flexible Configuration**: YAML-based configuration compatible with asimov workflows
- **Cluster Integration**: Submit jobs to HTCondor clusters via asimov

## Usage

### Basic Setup

1. Create an asimov project:
```bash
mkdir my-analysis
cd my-analysis
asimov init "My Analysis"
```

2. Create a jim configuration file (see `example/asimov_example_config.yaml` for a template)

3. Add the configuration to asimov's ledger

4. Build and submit the job:
```bash
asimov manage build
asimov manage submit
```

### Using External PSDs

To use PSDs from a previous analysis, add the `psd_files` section to your configuration:

```yaml
psd_files:
  H1: /path/to/previous_analysis/H1_psd.npz
  L1: /path/to/previous_analysis/L1_psd.npz
```

The PSD files should be in the format produced by `PowerSpectrum.to_file()`, which is a `.npz` file containing:
- `values`: PSD values
- `frequencies`: Corresponding frequencies
- `name`: Detector name

### Using External Data Files

To use data from a previous analysis, add the `data_files` section to your configuration:

```yaml
data_files:
  H1: /path/to/previous_analysis/H1_data.npz
  L1: /path/to/previous_analysis/L1_data.npz
```

The data files should be in the format produced by `Data.to_file()`, which is a `.npz` file containing:
- `td`: Time-domain data
- `dt`: Time step
- `epoch`: GPS epoch
- `name`: Detector name

### Programmatic Use

You can also use the asimov interface programmatically:

```python
from asimov.pipelines import known_pipelines

# Get the jim pipeline class
JimPipeline = known_pipelines['jim']

# Create a pipeline instance
pipeline = JimPipeline(production)

# Build configuration with external PSDs
psds = {
    'H1': '/path/to/H1_psd.npz',
    'L1': '/path/to/L1_psd.npz'
}

data_files = {
    'H1': '/path/to/H1_data.npz',
    'L1': '/path/to/L1_data.npz'
}

pipeline.build_dag(psds=psds, data_files=data_files)

# Submit the job
cluster_id, logger = pipeline.submit_dag()
```

## Configuration File Format

The configuration file is a YAML file with the following main sections:

### Event Parameters
- `gps`: GPS time of the event
- `segment_length`: Length of data segment
- `post_trigger_length`: Length after trigger time
- `f_min`, `f_max`: Frequency range
- `f_ref`: Reference frequency
- `ifos`: List of detectors (e.g., `['H1', 'L1']`)

### Data Sources (Optional)
- `psd_files`: Dictionary mapping detector names to PSD file paths
- `data_files`: Dictionary mapping detector names to data file paths

### Sampler Settings
- `seed`: Random seed
- `n_chains`: Number of MCMC chains
- `n_local_steps`, `n_global_steps`: MCMC steps
- `n_training_loops`, `n_production_loops`: Training and production loops
- Various other flowMC parameters

### Prior Ranges
- `M_c_range`: Chirp mass range
- `q_range`: Mass ratio range
- `max_s1`, `max_s2`: Maximum spin magnitudes
- Other parameter ranges (see example)

## Output

After completion, jim will produce:

- `results/samples.npz`: Posterior samples
- `results/corner.jpeg`: Corner plot
- `results/loss.jpeg`: Training loss plot
- `results/acceptance_rates.jpeg`: Acceptance rate plots

## See Also

- [asimov documentation](https://asimov.docs.ligo.org/)
- [jim documentation](https://jim.readthedocs.io/)
- Example configuration: `example/asimov_example_config.yaml`
