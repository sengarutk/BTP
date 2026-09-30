"""Edge/cloud streaming processes and the runtime policy switchboard."""
from .cloud_pipeline import CloudPipeline
from .edge_pipeline import EdgePipeline

__all__ = ["EdgePipeline", "CloudPipeline"]
