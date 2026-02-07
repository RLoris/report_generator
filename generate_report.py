#!/usr/bin/env python3

"""
Report Generator
Generates a raw report of submitted + pending changes for a specific date range (P4).
Optionally, generates an AI report based on the raw report generated.
"""

import os
import subprocess
import sys
import argparse
from datetime import datetime
from io import StringIO
import requests
from utilities.decorators import timed

def run_p4_command(p4_user, p4_workspace, p4_server, command):
    """Run a p4 command and return the output."""
    cmd = ['p4', '-u', p4_user, '-c', p4_workspace, '-p', p4_server] + command
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running p4 command: {e}", file=sys.stderr)
        print(f"Output: {e.stderr}", file=sys.stderr)
        sys.exit(1)

def get_workspace_depot_paths(p4_user, p4_workspace, p4_server):
    """Get depot paths from workspace."""
    output = run_p4_command(p4_user, p4_workspace, p4_server, ['client', '-o', p4_workspace])

    depot_paths = []
    in_view_section = False

    for line in output.split('\n'):
        if line.startswith('View:'):
            in_view_section = True
            continue

        if in_view_section:
            # Parse line: "	//depot/path/... //client/path/..."
            line = line.strip()
            if not line:
                continue
            if line.startswith('//'):
                # Extract depot path (first part before space)
                parts = line.split()
                if parts:
                    depot_path = parts[0]
                    # Remove any exclusion markers (-)
                    if not depot_path.startswith('-'):
                        depot_paths.append(depot_path)
            else:
                break

    return depot_paths

def parse_pending_changes(output, start_date, end_date):
    """Parse pending changes and filter by date range."""
    lines = output.split('\n')
    changes = []
    current_change = None

    # Convert dates to comparable format YYYY-MM-DD vs YYYY/MM/DD
    start_date_str = start_date.replace('-', '/')
    end_date_str = end_date.replace('-', '/') if end_date else None

    for line in lines:
        # Check for change keyword: "Change 12345 on 2000/12/31 by user@workspace"
        if line.startswith('Change '):
            # Save previous change if it matches our date range
            if current_change:
                change_date = current_change['date']
                in_range = change_date >= start_date_str
                if end_date_str:
                    in_range = in_range and change_date <= end_date_str
                if in_range:
                    changes.append(current_change)

            # Parse new change
            parts = line.split()
            if len(parts) >= 4:
                current_change = {
                    'number': parts[1],
                    'date': parts[3],
                    'header': line,
                    'description': []
                }
        elif current_change and line.startswith('\t'):
            # Add the description (indented with tab)
            current_change['description'].append(line)

    # Process the last change
    if current_change:
        change_date = current_change['date']
        in_range = change_date >= start_date_str
        if end_date_str:
            in_range = in_range and change_date <= end_date_str
        if in_range:
            changes.append(current_change)

    return changes

@timed
def generate_raw_report(p4_user, p4_workspace, p4_server, start_date, end_date=None, depot_paths=None):
    """Generate the raw report and return as string."""

    # If no depot paths specified, get them from workspace
    if not depot_paths:
        depot_paths = get_workspace_depot_paths(p4_user, p4_workspace, p4_server)
        if not depot_paths:
            print("Warning: Could not determine depot paths from workspace, using all depots", file=sys.stderr)
            depot_paths = None

    # Build path filter for commands
    path_filter = []
    if depot_paths:
        path_filter = depot_paths

    # Convert dates to P4 format YYYY-MM-DD vs YYYY/MM/DD
    p4_start_date = start_date.replace('-', '/')
    p4_end_date = end_date.replace('-', '/') if end_date else 'now'

    # Get pending changes
    pending_cmd = ['changes', '-l', '-u', p4_user, '-s', 'pending']
    if path_filter:
        pending_cmd.extend(path_filter)

    pending_output = run_p4_command(
        p4_user, p4_workspace, p4_server, pending_cmd
    )
    pending_changes = parse_pending_changes(pending_output, start_date, end_date)

    # Get submitted changes
    submitted_cmd = ['changes', '-u', p4_user, '-s', 'submitted']
    if path_filter:
        for path in path_filter:
            submitted_cmd.append(f'{path}@{p4_start_date},@{p4_end_date}')
    else:
        submitted_cmd.append(f'@{p4_start_date},@{p4_end_date}')

    submitted_output = run_p4_command(
        p4_user, p4_workspace, p4_server, submitted_cmd
    )
    submitted_count = len([line for line in submitted_output.split('\n') if line.startswith('Change ')])

    report = StringIO()

    # Print report metadata
    report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report.write(f"{'='*60}\n")
    report.write("P4 CHANGES REPORT\n")
    report.write(f"Date: {start_date} to {end_date if end_date else report_date}\n")
    report.write(f"User: {p4_user} | Workspace: {p4_workspace} | Server: {p4_server}\n")
    report.write(f"Generated: {report_date}\n")
    report.write(f"Pending: {len(pending_changes)} | Submitted: {submitted_count}\n")
    report.write(f"{'='*60}\n\n")

    # Add pending changes
    if pending_changes:
        for change in pending_changes:
            report.write(f"\n{change['header']}\n")
            for desc_line in change['description']:
                report.write(f"{desc_line}\n")
    else:
        report.write("No pending changes found for this period.\n")

    # Add submitted changes
    submitted_cmd_full = ['changes', '-l', '-u', p4_user, '-s', 'submitted']
    if path_filter:
        for path in path_filter:
            submitted_cmd_full.append(f'{path}@{p4_start_date},@{p4_end_date}')
    else:
        submitted_cmd_full.append(f'@{p4_start_date},@{p4_end_date}')

    submitted_output_full = run_p4_command(
        p4_user, p4_workspace, p4_server, submitted_cmd_full
    )

    if submitted_output_full.strip():
        report.write(f"{submitted_output_full}\n")
    else:
        report.write("No submitted changes found for this period.\n")

    return report.getvalue()

@timed
def generate_ai_report(report_text, ollama_url, model, custom_prompt):
    """Send raw report along user prompt to Ollama."""

    prompt = f"""{custom_prompt}\n\n{report_text}"""

    # Send request to ollama and wait for response... Can be very long !
    try:
        # Token context for the prompt + response, then get closest power of 2
        num_ctx = int((len(prompt) / 3) * 2)
        num_ctx = 1 << (num_ctx - 1).bit_length()

        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1, # Deterministic
                    "num_ctx": num_ctx
                }
            }
        )
        response.raise_for_status()
        result = response.json()
        return result.get('response', 'No AI report generated')
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Ollama: {e}", file=sys.stderr)
        print(f"Make sure Ollama is running at {ollama_url}", file=sys.stderr)
        return None

def main():
    # Get inputs from user
    parser = argparse.ArgumentParser(
        description='Generate a dev report with the help of a local AI model',
        epilog='Date format: YYYY-MM-DD (e.g., 2000-12-31)'
    )
    parser.add_argument('-u', '--user', required=True, help='P4 username')
    parser.add_argument('-w', '--workspace', required=True, help='P4 workspace')
    parser.add_argument('-r', '--server', required=True, help='P4 remote url:port')
    parser.add_argument('-s', '--start-date', required=True, help='Start date (YYYY-MM-DD, required)')
    parser.add_argument('-e', '--end-date', help='End date (YYYY-MM-DD, optional, defaults to now)')
    parser.add_argument('-d', '--depot', action='append', help='Depot path(s) to filter (e.g., //depot/main/...). Can be specified multiple times. If not provided, will use workspace depot paths.')
    parser.add_argument('--raw-output', help='Save raw report into this file (required for raw report)')
    parser.add_argument('--ai-output', help='Save AI report into this file (required for AI report)')
    parser.add_argument('--ollama-url', default='http://localhost:11434', help='Ollama API URL (default: http://localhost:11434)')
    parser.add_argument('--ollama-model', default='qwen2.5:14b', help='Ollama model to use (default: qwen2.5:14b)')
    parser.add_argument('--prompt-file', help='Path to a file containing the custom prompt for AI report (required for AI report)')
    parser.add_argument('--raw-reuse', action="store_true", help='Skip the raw report generation if it already exists at that path')
    args = parser.parse_args()

    # Sanitize inputs
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        if args.end_date:
            datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        print("Error: Invalid date format. Use YYYY-MM-DD (e.g., 2000-12-31)", file=sys.stderr)
        sys.exit(1)

    raw_report = None
    if args.raw_output and args.raw_reuse and os.path.isfile(args.raw_output):

        # Load raw report
        try:
            with open(args.raw_output, 'r', encoding='utf-8') as f:
                raw_report = f.read()
            print(f"Reusing raw report file: {args.raw_output}", file=sys.stderr)    
        except Exception as e:
            print(f"Error reading raw report file: {e}", file=sys.stderr)
            sys.exit(1)
    else:

        # Generate the raw report
        print("Generating raw P4 report...", file=sys.stderr)
        raw_report = generate_raw_report(
            args.user, args.workspace, args.server, args.start_date, args.end_date, args.depot
        )

        # Save raw report
        if args.raw_output:
            with open(args.raw_output, 'w', encoding='utf-8') as f:
                f.write(raw_report)
            print(f"Raw report saved to: {args.raw_output}", file=sys.stderr)

    # Generate AI report if requested (prompt + output must be set)
    if args.prompt_file and args.ai_output:

        # Get custom prompt from file
        custom_prompt = None
        try:
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                custom_prompt = f.read()
        except Exception as e:
            print(f"Error reading custom prompt file: {e}", file=sys.stderr)
            sys.exit(1)

        summary = None
        # Generate report using ollama
        if custom_prompt:
            print(f"Generating AI report using {args.ollama_model}...", file=sys.stderr)
            summary = generate_ai_report(
                raw_report, args.ollama_url, args.ollama_model, custom_prompt
            )

            if not summary:
                print("Warning: Could not generate AI report", file=sys.stderr)
                sys.exit(1)

            # Save AI report
            with open(args.ai_output, 'w', encoding='utf-8') as f:
                f.write(summary)
            print(f"AI report saved to: {args.ai_output}", file=sys.stderr)            

# Script entrypoint
if __name__ == '__main__':
    main()
