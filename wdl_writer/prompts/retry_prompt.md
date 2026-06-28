The WDL you just generated failed validation with these errors from `sprocket check`:

{{stderr}}

Please regenerate the WDL with these errors fixed. Follow these rules strictly:
- Only use inputs that are explicitly defined in the task definitions provided. Do not invent or guess input names.
- If a task call includes an input that does not exist in the task definition, remove it entirely from the call — do not rename it.
- Do not add new tasks, change the workflow structure, or modify anything unrelated to the errors above.

Respond only with the corrected WDL inside a ```wdl code block.
