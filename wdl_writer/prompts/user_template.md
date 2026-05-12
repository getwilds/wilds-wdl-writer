Generate a WILDS WDL pipeline named `ww-{{pipeline_name}}` that combines the following WILDS WDL Library modules into a single workflow.

Pipeline name: ww-{{pipeline_name}}
Workflow name (inside the WDL): {{workflow_name}}
Modules to combine: {{modules}}

Analysis goal: {{analysis_goal}}
Input data type: {{input_data_type}}
Organism: {{organism}}
Reference genome: {{reference_genome}}

Import each module from the WILDS WDL Library using the `refs/heads/main` raw GitHub URL pattern, wire each module's task outputs to the next module's task inputs, and collect the final outputs at the workflow level. Use ONLY tasks from the listed modules — do not define new custom tasks.
