"""Jim pipeline specification for asimov."""

import glob
import os
import re
import shutil
import subprocess
import yaml

try:
    from asimov.pipeline import Pipeline, PipelineException, PipelineLogger
except ImportError:
    raise ImportError(
        "asimov is required to use the jim asimov interface. "
        "Install it with: pip install asimov"
    )

# Check if this is asimov v0.7+ with prior interface support
try:
    from asimov.priors import PriorInterface
    ASIMOV_V07_SUPPORT = True
except ImportError:
    ASIMOV_V07_SUPPORT = False


class Jim(Pipeline):
    """
    The Jim Pipeline interface for asimov.

    This pipeline allows automated inference with jim through asimov,
    with support for:
    - PSDs from previous analyses
    - Frame files containing GW data from previous analyses
    - Flexible configuration through YAML files

    Parameters
    ----------
    production : :class:`asimov.Production`
        The production object from asimov.
    category : str, optional
        The category of the job.
        Defaults to "C01_offline".
    """

    name = "jim"
    STATUS = {"wait", "stuck", "stopped", "running", "finished"}

    def __init__(self, production, category=None):
        super(Jim, self).__init__(production, category)
        self.logger.info("Using the jim pipeline")

        if not production.pipeline.lower() == "jim":
            raise PipelineException("Pipeline mismatch")
        
        # Initialize prior interface for v0.7+ compatibility
        if ASIMOV_V07_SUPPORT:
            self._prior_interface = None

    def detect_completion(self):
        """
        Check for the production of result files to signal that the job has completed.
        
        Returns
        -------
        bool
            True if the job has completed, False otherwise.
        """
        self.logger.info("Checking if the jim job has completed")
        
        # Check for the existence of result files
        if not self.production.rundir:
            self.logger.info("No rundir specified")
            return False
            
        results_dir = os.path.join(self.production.rundir, "results")
        if not os.path.exists(results_dir):
            self.logger.info("No results directory found")
            return False
        
        # Look for common result file patterns
        result_patterns = [
            "samples_*.npz",
            "samples_*.h5",
            "samples_*.hdf5",
            "posterior_*.json",
        ]
        
        for pattern in result_patterns:
            results_files = glob.glob(os.path.join(results_dir, pattern))
            if len(results_files) > 0:
                self.logger.info(f"Results files found: {results_files}")
                return True
        
        self.logger.info("No results files found.")
        return False

    def build_dag(self, psds=None, data_files=None, user=None, dryrun=False):
        """
        Construct configuration and submission script for jim.

        Parameters
        ----------
        psds : dict, optional
            Dictionary mapping detector names to PSD file paths.
            If provided, these PSDs from previous analyses will be used.
            Example: {"H1": "/path/to/H1_psd.npz", "L1": "/path/to/L1_psd.npz"}
        data_files : dict, optional
            Dictionary mapping detector names to frame/data file paths.
            If provided, these data files from previous analyses will be used.
            Example: {"H1": "/path/to/H1_data.npz", "L1": "/path/to/L1_data.npz"}
        user : str, optional
            The user accounting tag which should be used to run the job.
        dryrun : bool, optional
            If set to True, the commands will not be run, but will be printed
            to standard output. Defaults to False.

        Raises
        ------
        PipelineException
            Raised if the construction of the configuration fails.
        """
        cwd = os.getcwd()
        self.logger.info(f"Working in {cwd}")

        # Get the configuration file
        if self.production.event.repository:
            config_file = self.production.event.repository.find_prods(
                self.production.name, self.category
            )[0]
            config_file = os.path.join(cwd, config_file)
        else:
            config_file = f"{self.production.name}.yaml"

        if not os.path.exists(config_file):
            raise PipelineException(
                f"Configuration file not found: {config_file}",
                production=self.production.name,
            )

        # Set up run directory
        if self.production.rundir:
            rundir = self.production.rundir
        else:
            rundir = os.path.join(
                os.path.expanduser("~"),
                self.production.event.name,
                self.production.name,
            )
            self.production.rundir = rundir

        os.makedirs(rundir, exist_ok=True)
        results_dir = os.path.join(rundir, "results")
        os.makedirs(results_dir, exist_ok=True)

        # Load the configuration
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        # Update configuration with PSDs if provided
        if psds is not None:
            self.logger.info(f"Using external PSDs: {psds}")
            # Create a data directory for PSDs
            psd_dir = os.path.join(rundir, "psds")
            os.makedirs(psd_dir, exist_ok=True)
            
            # Copy PSD files to rundir and update config
            config["psd_files"] = {}
            for ifo, psd_path in psds.items():
                if os.path.exists(psd_path):
                    dest_path = os.path.join(psd_dir, f"{ifo}_psd.npz")
                    if not dryrun:
                        shutil.copy(psd_path, dest_path)
                    config["psd_files"][ifo] = dest_path
                    self.logger.info(f"Copied PSD for {ifo} to {dest_path}")
                else:
                    self.logger.warning(f"PSD file not found: {psd_path}")

        # Update configuration with data files if provided
        if data_files is not None:
            self.logger.info(f"Using external data files: {data_files}")
            # Create a data directory
            data_dir = os.path.join(rundir, "data")
            os.makedirs(data_dir, exist_ok=True)
            
            # Copy data files to rundir and update config
            config["data_files"] = {}
            for ifo, data_path in data_files.items():
                if os.path.exists(data_path):
                    dest_path = os.path.join(data_dir, f"{ifo}_data.npz")
                    if not dryrun:
                        shutil.copy(data_path, dest_path)
                    config["data_files"][ifo] = dest_path
                    self.logger.info(f"Copied data for {ifo} to {dest_path}")
                else:
                    self.logger.warning(f"Data file not found: {data_path}")

        # Update working directory in config
        config["working_dir"] = results_dir

        # Write the updated configuration
        updated_config_file = os.path.join(rundir, "config.yaml")
        if not dryrun:
            with open(updated_config_file, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            self.logger.info(f"Updated configuration written to {updated_config_file}")

        # Create a submission script
        submit_script = os.path.join(rundir, "submit.sh")
        
        # Create a separate Python script for execution
        run_script = os.path.join(rundir, "run_jim.py")
        run_script_content = f"""#!/usr/bin/env python
\"\"\"Jim analysis execution script - generated by asimov\"\"\"

from jimgw.run.single_event_run_manager import SingleEventRunManager
from jimgw.run.library.IMRPhenomPv2_standard_cbc import IMRPhenomPv2StandardCBCRunDefinition
import numpy as np

# Load configuration
run = IMRPhenomPv2StandardCBCRunDefinition.from_file('{updated_config_file}')

# Create run manager and execute
manager = SingleEventRunManager(run)
manager.sample()

# Save results
samples = manager.get_chain_samples()
np.savez('{results_dir}/samples.npz', **samples)

# Generate plots
manager.plot_chains()
manager.plot_loss()
manager.plot_acceptances()

print('Jim analysis completed successfully!')
"""
        
        submit_content = f"""#!/bin/bash
#
# Jim analysis submission script
# Generated by asimov
#

set -e

cd {rundir}

# Run jim analysis
python run_jim.py

echo "Analysis completed"
"""

        if not dryrun:
            with open(run_script, "w") as f:
                f.write(run_script_content)
            os.chmod(run_script, 0o755)
            
            with open(submit_script, "w") as f:
                f.write(submit_content)
            os.chmod(submit_script, 0o755)
            self.logger.info(f"Submission script written to {submit_script}")
            self.logger.info(f"Run script written to {run_script}")
        else:
            self.logger.info("Dry run - would create:")
            self.logger.info(f"  Config: {updated_config_file}")
            self.logger.info(f"  Run script: {run_script}")
            self.logger.info(f"  Submit script: {submit_script}")

        return PipelineLogger(
            message=f"Jim configuration prepared in {rundir}",
            production=self.production.name,
        )

    def submit_dag(self, dryrun=False):
        """
        Submit the jim job to the cluster.

        Parameters
        ----------
        dryrun : bool, optional
            If set to True, the job will not be submitted,
            but all commands will be printed to standard output.
            Defaults to False.

        Returns
        -------
        int
            The cluster ID assigned to the running job.
        PipelineLogger
            The pipeline logger message.

        Raises
        ------
        PipelineException
            Raised if the pipeline fails to submit the job.
        """
        cwd = os.getcwd()
        self.logger.info(f"Working in {cwd}")

        self.before_submit()

        submit_script = os.path.join(self.production.rundir, "submit.sh")
        
        if not os.path.exists(submit_script):
            raise PipelineException(
                f"Submission script not found: {submit_script}. "
                "Did you run build_dag first?",
                production=self.production.name,
            )

        # Create a condor submit file
        condor_submit_file = os.path.join(self.production.rundir, "submit.sub")
        
        # Get job label
        if "job label" in self.production.meta:
            job_label = self.production.meta["job label"]
        else:
            job_label = self.production.name

        condor_content = f"""# Jim condor submit file
universe = vanilla
executable = {submit_script}
output = {self.production.rundir}/jim.out
error = {self.production.rundir}/jim.err
log = {self.production.rundir}/jim.log
getenv = True
request_memory = 8GB
request_cpus = 4

# Accounting
+JobBatchName = "jim/{self.production.event.name}/{self.production.name}"
"""

        if "accounting group" in self.production.meta.get("scheduler", {}):
            condor_content += f"accounting_group = {self.production.meta['scheduler']['accounting group']}\n"

        condor_content += "\nqueue 1\n"

        if not dryrun:
            with open(condor_submit_file, "w") as f:
                f.write(condor_content)
            self.logger.info(f"Condor submit file written to {condor_submit_file}")

        # Submit to condor
        command = ["condor_submit", condor_submit_file]

        if dryrun:
            print(" ".join(command))
            return None, PipelineLogger(
                message="Dry run - job not submitted",
                production=self.production.name,
            )
        else:
            try:
                self.logger.info(f"Submitting: {' '.join(command)}")
                
                result = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
                )
                stdout, stderr = result.communicate()
                
                stdout_str = stdout.decode() if stdout else ""
                
                if "submitted to cluster" in stdout_str:
                    # Extract cluster ID
                    match = re.search(r"submitted to cluster ([\d]+)", stdout_str)
                    if match:
                        cluster = int(match.groups()[0])
                        self.logger.info(
                            f"Submitted successfully. Running with job id {cluster}"
                        )
                        self.production.status = "running"
                        self.production.job_id = cluster
                        return cluster, PipelineLogger(
                            message=stdout_str,
                            production=self.production.name,
                        )
                
                self.logger.error("Could not submit the job to the cluster")
                self.logger.info(stdout_str)
                if stderr:
                    self.logger.error(stderr.decode())
                
                raise PipelineException(
                    f"The job could not be submitted.\n{stdout_str}",
                    production=self.production.name,
                )
                
            except FileNotFoundError as error:
                self.logger.exception(error)
                raise PipelineException(
                    "It looks like condor isn't installed on this system.\n"
                    f"I wanted to run {' '.join(command)}."
                ) from error

    def collect_assets(self):
        """
        Gather all of the result assets for this job.
        
        Returns
        -------
        dict
            Dictionary containing paths to result files.
        """
        return {
            "samples": self.samples(),
            "config": os.path.join(self.production.rundir, "config.yaml"),
            "plots": self.plots(),
        }

    def samples(self, absolute=False):
        """
        Collect the samples file.
        
        Parameters
        ----------
        absolute : bool, optional
            If True, return absolute paths. Defaults to False.
        
        Returns
        -------
        list
            List of paths to sample files.
        """
        if absolute:
            rundir = os.path.abspath(self.production.rundir)
        else:
            rundir = self.production.rundir
        
        results_dir = os.path.join(rundir, "results")
        self.logger.info(f"Looking for samples in: {results_dir}")
        
        samples = glob.glob(os.path.join(results_dir, "samples*.npz"))
        samples += glob.glob(os.path.join(results_dir, "samples*.h5"))
        samples += glob.glob(os.path.join(results_dir, "samples*.hdf5"))
        
        return samples

    def plots(self, absolute=False):
        """
        Collect the plot files.
        
        Parameters
        ----------
        absolute : bool, optional
            If True, return absolute paths. Defaults to False.
        
        Returns
        -------
        list
            List of paths to plot files.
        """
        if absolute:
            rundir = os.path.abspath(self.production.rundir)
        else:
            rundir = self.production.rundir
        
        results_dir = os.path.join(rundir, "results")
        
        plots = glob.glob(os.path.join(results_dir, "*.jpeg"))
        plots += glob.glob(os.path.join(results_dir, "*.png"))
        plots += glob.glob(os.path.join(results_dir, "*.pdf"))
        
        return plots

    def after_completion(self):
        """
        Hook to run after the job has completed successfully.
        """
        self.logger.info("Jim job has completed.")
        self.production.status = "finished"
    
    def get_prior_interface(self):
        """
        Get the prior interface for jim pipeline (v0.7+ compatibility).
        
        This provides compatibility with asimov v0.7 and later which support
        standardized prior interfaces.
        
        Returns
        -------
        PriorInterface or None
            The prior interface if asimov v0.7+ is installed, None otherwise
        """
        if not ASIMOV_V07_SUPPORT:
            return None
        
        if self._prior_interface is None:
            # Create a basic prior interface for jim
            # Jim uses YAML configuration files, so we can provide
            # a simple wrapper that extracts prior information
            try:
                from asimov.priors import PriorInterface
                priors = getattr(self.production, 'priors', None)
                if priors:
                    self._prior_interface = PriorInterface(priors)
            except Exception as e:
                self.logger.warning(f"Could not create prior interface: {e}")
                return None
        
        return self._prior_interface

    def clean(self, dryrun=False):
        """
        Remove all of the artifacts from a job from the working directory.
        
        Parameters
        ----------
        dryrun : bool, optional
            If True, only print what would be removed. Defaults to False.
        """
        if not self.production.rundir:
            self.logger.warning("No rundir specified, cannot clean.")
            return
        
        if dryrun:
            self.logger.info(f"Would remove: {self.production.rundir}")
        else:
            if os.path.exists(self.production.rundir):
                shutil.rmtree(self.production.rundir)
                self.logger.info(f"Removed {self.production.rundir}")
