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
- **GWF Frame Files**: Read gravitational wave data from standard GWF (Gravitational Wave Frame) files
- **Liquid Templating**: Configuration generated via liquid templates (like bilby pipeline)
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

2. Configure your production in asimov's ledger with the required metadata

3. Build and submit the job:
```bash
asimov manage build
asimov manage submit
```

### Using External PSDs

PSDs from previous analyses can be provided via asimov's production metadata or through the `psds` argument to `build_dag()`:

```python
pipeline.build_dag(psds={
    'H1': '/path/to/H1_psd.dat',
    'L1': '/path/to/L1_psd.dat'
})
```

The PSD files should be in NPZ format produced by `PowerSpectrum.to_file()`, containing:
- `values`: PSD values
- `frequencies`: Corresponding frequencies
- `name`: Detector name

### Using GWF Frame Files

Jim now supports reading data from standard GWF (Gravitational Wave Frame) files, which is the standard format for gravitational wave data:

```yaml
data_files:
  H1: /path/to/H1_frame_cache.gwf
  L1: /path/to/L1_frame_cache.gwf

# Channel names are required for GWF files
channels:
  H1: H1:GDS-CALIB_STRAIN
  L1: L1:GDS-CALIB_STRAIN
```

You can also provide frame files via the `data_files` argument to `build_dag()`:

```python
pipeline.build_dag(
    data_files={
        'H1': '/path/to/H1.gwf',
        'L1': '/path/to/L1.gwf'
    }
)
```

The jim pipeline will automatically detect GWF files (by `.gwf` or `.lcf` extension) and read them using gwpy's `TimeSeries.read()` method.

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
