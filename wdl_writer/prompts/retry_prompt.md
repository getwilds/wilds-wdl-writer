The WDL you just generated failed validation with these errors from `sprocket check`:

{{stderr}}

Please regenerate the WDL with these errors fixed. Follow these rules strictly:
- Only use input and output names that are explicitly defined in the task definitions provided. Do not invent or guess input or output names.
- If a task call includes an input that does not exist in the task definition, remove it entirely from the call. Do not rename it.
- If the workflow references a task output that does not exist in the task definition, correct it to match the exact output name defined in the task. Do not invent a new name.
- Do not add new tasks, change the workflow structure, or modify anything unrelated to the errors above.

Respond only with the corrected WDL inside a ```wdl code block.
