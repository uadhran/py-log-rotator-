from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.email import EmailOperator
from airflow.models import Variable
from datetime import datetime, timedelta
from src.log_rotator.core import process_logs, load_config  # Import from core
import os
import logging
import jinja2  # For HTML email templates

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 9, 4),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'advanced_log_management',
    default_args=default_args,
    description='Orchestrated log rotation and management',
    schedule_interval='*/30 * * * *',  # Every 30 minutes
    catchup=False,
    max_active_runs=1,
    tags=['logs', 'rotation'],
    sla=timedelta(minutes=30),  # SLA monitoring
)

def health_check(**context):
    """Pre-flight health check."""
    # Check disk space, permissions, etc.
    if os.path.exists('/var/log') and os.access('/var/log', os.W_OK):
        logging.info("Health check passed.")
        return 'execution_mode_decision'
    else:
        logging.error("Health check failed.")
        return 'send_error_email'

def execution_mode_decision(**context):
    """Decide mode: report or full execution."""
    # For simplicity, always full execution; customize as needed
    return 'manage_logs'

def manage_logs(**context):
    """Process logs using core.py logic."""
    config_data = Variable.get('scattered_log_configs')
    report = process_logs(config_data=config_data, dry_run=False)
    context['ti'].xcom_push(key='report', value=report)
    return report

def aggregate_results(**context):
    """Aggregate results from parallel tasks (if any)."""
    report = context['ti'].xcom_pull(key='report')
    return report

def render_email_task(**context):
    """Render email HTML from report data."""
    # HTML email template
    email_template = """
<!DOCTYPE html>
<html>
<head><style>
    body {font-family: Arial, sans-serif; padding: 20px;}
    .status {color: green; font-weight: bold;}
    table {border-collapse: collapse; width: 100%; margin: 20px 0;}
    th, td {border: 1px solid #ddd; padding: 8px; text-align: left;}
    th {background-color: #4CAF50; color: white;}
</style></head>
<body>
<h1>Log Rotation Report</h1>
<p>Status: <span class="status">Success</span></p>
<table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Directories Managed</td><td>{{ directories_managed }}</td></tr>
    <tr><td>Files Processed</td><td>{{ files_processed }}</td></tr>
    <tr><td>Files Rotated</td><td>{{ files_rotated }}</td></tr>
    <tr><td>Files Compressed</td><td>{{ files_compressed }}</td></tr>
    <tr><td>Files Deleted</td><td>{{ files_deleted }}</td></tr>
    <tr><td>Space Freed</td><td>{{ space_freed_mb }} MB</td></tr>
</table>
<p><small>Report generated at: {{ timestamp }}</small></p>
</body>
</html>
"""

    report = context['ti'].xcom_pull(task_ids='aggregate_results')
    if not report:
        report = {
            'directories_managed': 0,
            'files_processed': 0,
            'files_rotated': 0,
            'files_compressed': 0,
            'files_deleted': 0,
            'space_freed_mb': 0,
            'timestamp': datetime.now().isoformat()
        }

    template = jinja2.Template(email_template)
    rendered_html = template.render(**report)
    context['ti'].xcom_push(key='email_html', value=rendered_html)
    return rendered_html

send_report_email = EmailOperator(
    task_id='send_report_email',
    to='your-email@company.com',  # Configure in airflow.cfg
    subject='Log Rotation Summary - {{ ds }}',
    html_content="{{ ti.xcom_pull(task_ids='render_email', key='email_html') }}",
    dag=dag,
)

send_error_email = EmailOperator(
    task_id='send_error_email',
    to='your-email@company.com',
    subject='Log Rotation Error',
    html_content='<h1>Error: Health check failed!</h1>',
    dag=dag,
)

# Task definitions
health_check_task = BranchPythonOperator(
    task_id='health_check',
    python_callable=health_check,
    dag=dag,
)

mode_decision_task = BranchPythonOperator(
    task_id='execution_mode_decision',
    python_callable=execution_mode_decision,
    dag=dag,
)

manage_logs_task = PythonOperator(
    task_id='manage_logs',
    python_callable=manage_logs,
    dag=dag,
)

aggregate_task = PythonOperator(
    task_id='aggregate_results',
    python_callable=aggregate_results,
    dag=dag,
)

render_email_task_op = PythonOperator(
    task_id='render_email',
    python_callable=render_email_task,
    dag=dag,
)

# Task flow
health_check_task >> mode_decision_task >> manage_logs_task >> aggregate_task >> render_email_task_op >> send_report_email
health_check_task >> send_error_email
