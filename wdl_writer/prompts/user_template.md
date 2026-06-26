Generate a WILDS WDL pipeline that combines the following WILDS WDL Library tasks into a single workflow.

Tasks to combine: {{tasks}}
Input data type: {{input_data_type}}
Input data format: {{format}}
Species: {{species}}

Import each module from the WILDS WDL Library using the `refs/heads/main` raw GitHub URL pattern, wire each module's task outputs to the next module's task inputs, and collect the final outputs at the workflow level. Use ONLY tasks from the listed modules — do not define new custom tasks.
