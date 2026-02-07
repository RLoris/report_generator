# Report Generator

![Showcase](./assets/ReportGeneratorShowcase.gif)

## What

This script generates a raw report for a specific date range using Perforce changes. Optionally, it can generate an AI report based on the raw report using ollama.

## How

Uses python, P4 and ollama to generate the final report.

## Why

Because when you repeat a task that takes time each month, automation becomes handy, even if you still need to verify the output !

## Setup

- Setup Python 3.12
- Setup and run Ollama (Pick a model you wish to use, eg: ollama pull qwen2.5:32b) 
- Setup and run P4 (Pick a workspace to base your report from, eg: MyWorkspace)
- Add a prompt base on your needs (summary, format, highlights) in prompts/... or use the default one (prompts/prompt.txt)
- Run this script :
    python generate_report.py -u MyUser -w MyWorkspace -r MyRemote:1666 -s 2026-01-01 --ollama-model qwen2.5:32b --raw-output ./raw_report.txt --ai-output ./ai_report.txt --prompt-file ./prompts/prompt.txt

## Todo

- Add Git support (branch)
- Add a GUI
- Find and match with video/screenshot of the feature/bug described

If you want to help, you are free to make a pull request !

## Note

The raw report should be detailed enough and safe to use, the ai report quality depends on the model you use (tested with mistral, llama3.2, qwen2.5:14b, qwen2.5:32b locally), best default is already set, please verify the final output !

This script is provided “as is”, without warranty of any kind, and the author is not responsible for any damage, data loss, or other issues resulting from its use.

## License

GNU AGPL V3
