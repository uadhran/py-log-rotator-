# py-log-rotator 🔄

> Python-based log rotation and management system with Airflow orchestration for distributed log files

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Airflow](https://img.shields.io/badge/Apache%20Airflow-2.0+-green.svg)](https://airflow.apache.org/)

## 🚀 Features

- 🗂️ **Scattered Log Management** - Handles logs distributed across multiple directories under a parent directory
- ⚡ **Airflow Orchestration** - Reliable scheduling with retry logic, SLA monitoring, and rich UI
- 📧 **Email Notifications** - Professional HTML reports with status alerts and detailed statistics
- 🔄 **Smart Rotation** - Size-based and age-based log rotation with automatic compression
- 📊 **Comprehensive Reporting** - Detailed cleanup summaries and directory breakdowns
- ⚙️ **Flexible Configuration** - Per-directory policies, custom patterns, and retention rules
- 🔍 **Auto-Discovery** - Automatically finds and manages logs in nested directory structures
- 💾 **Space Optimization** - Gzip compression and intelligent cleanup to save disk space

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage](#usage)
- [Airflow Integration](#airflow-integration)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🛠️ Installation

### Prerequisites

- Python 3.7+
- Apache Airflow 2.0+
- SMTP server access (for email notifications)

### Install Dependencies

```bash
# Clone the repository
git clone https://github.com/yourusername/py-log-rotator.git
cd py-log-rotator

# Install Python dependencies
pip install -r requirements.txt

# Make scripts executable
chmod +x src/log_rotator/core.py
```

### Airflow Setup

```bash
# Copy DAG to Airflow DAGs directory
cp dags/log_management_dag.py $AIRFLOW_HOME/dags/

# Set Airflow variables
airflow variables set scattered_log_configs "$(cat configs/log_configs.json)"
```

## ⚡ Quick Start

### 1. Basic Usage (Standalone)

```bash
# Generate summary report
python3 src/log_rotator/core.py --parent-dir /var/log --report

# Dry run to see what would be cleaned
python3 src/log_rotator/core.py --parent-dir /var/log --dry-run

# Perform actual log rotation
python3 src/log_rotator/core.py --parent-dir /var/log
```

### 2. Airflow Integration

```bash
# Configure email settings in airflow.cfg
nano $AIRFLOW_HOME/airflow.cfg

# Enable the DAG
airflow dags unpause advanced_log_management

# Trigger manual run
airflow dags trigger advanced_log_management
```

## ⚙️ Configuration

### Log Configuration Structure

Create or update your log configuration in Airflow Variables:

```json
[
    {
        "name": "application_logs",
        "parent_directory": "/var/log/myapp",
        "subdirectory_configs": {
            "api": {
                "max_size_mb": 100,
                "max_age_days": 7,
                "pattern": "*.log"
            },
            "database": {
                "max_size_mb": 200,
                "max_age_days": 14,
                "pattern": "*.log"
            },
            "nginx": {
                "max_size_mb": 500,
                "max_age_days": 30,
                "pattern": "*.log"
            },
            "default": {
                "max_size_mb": 50,
                "max_age_days": 7,
                "pattern": "*.log"
            }
        },
        "enabled": true
    }
]
```

### Email Configuration

Edit `$AIRFLOW_HOME/airflow.cfg`:

```ini
[email]
email_backend = airflow.utils.email.send_email_smtp

[smtp]
smtp_host = smtp.gmail.com
smtp_starttls = True
smtp_ssl = False
smtp_user = your-email@company.com
smtp_password = your-app-password
smtp_port = 587
smtp_mail_from = your-email@company.com
```

## 📚 Usage

### Directory Structure Example

```
/var/log/myapp/                 # Parent directory
├── api/
│   ├── app.log                 # 150MB (needs rotation)
│   ├── error.log              # 25MB
│   └── access.log             # 80MB
├── database/
│   ├── mysql.log              # 300MB (needs rotation)
│   ├── slow-query.log         # 45MB
│   └── error.log              # 12MB (15 days old - needs cleanup)
├── nginx/
│   ├── access.log             # 400MB
│   └── error.log              # 30MB
└── background-jobs/
    ├── scheduler.log          # 60MB
    └── worker.log             # 35MB
```

### What py-log-rotator Does

1. **Discovery**: Automatically finds all subdirectories with log files
2. **Configuration Matching**: Applies appropriate policies based on directory names
3. **Size-based Rotation**: Rotates files exceeding size limits
4. **Age-based Cleanup**: Removes files older than retention period
5. **Compression**: Compresses rotated files to save space
6. **Reporting**: Generates detailed reports and sends email notifications

### Command Line Options

```bash
# Core script options
python3 src/log_rotator/core.py --help

Options:
  --parent-dir PATH        Parent directory containing scattered logs (required)
  --config-file FILE       JSON configuration file
  --report                 Generate summary report only
  --dry-run               Show what would be done without making changes
  --help                  Show this help message
```

## 🔄 Airflow Integration

### DAG Features

- **Scheduled Execution**: Runs every 30 minutes (configurable)
- **Health Checks**: Pre-flight system health validation
- **Parallel Processing**: Manages multiple parent directories simultaneously  
- **Error Handling**: Robust error handling with retries
- **SLA Monitoring**: 30-minute SLA with automatic alerts
- **Email Reports**: Rich HTML email notifications

### Task Flow

```
Start → Health Check → Execution Mode Decision → Log Discovery → 
Parallel Log Management → Results Aggregation → Email Report → Cleanup → End
```

### Monitoring

Access the Airflow UI to monitor:
- Task execution status
- Logs and error messages
- Execution duration and performance
- SLA compliance
- Email notification history

## 📖 Examples

### Example 1: Web Application Logs

```json
{
    "name": "webapp_logs",
    "parent_directory": "/var/log/webapp",
    "subdirectory_configs": {
        "api": {"max_size_mb": 100, "max_age_days": 7, "pattern": "*.log"},
        "frontend": {"max_size_mb": 50, "max_age_days": 3, "pattern": "*.log"},
        "backend": {"max_size_mb": 200, "max_age_days": 14, "pattern": "*.log"}
    },
    "enabled": true
}
```

### Example 2: System Logs

```json
{
    "name": "system_logs",
    "parent_directory": "/var/log",
    "subdirectory_configs": {
        "nginx": {"max_size_mb": 500, "max_age_days": 30, "pattern": "*.log"},
        "mysql": {"max_size_mb": 300, "max_age_days": 14, "pattern": "*.log"},
        "redis": {"max_size_mb": 100, "max_age_days": 7, "pattern": "*.log"},
        "default": {"max_size_mb": 50, "max_age_days": 7, "pattern": "*log"}
    },
    "enabled": true
}
```

### Example 3: Custom Configuration File

```bash
# Create custom config
cat > my_log_config.json << 'EOF'
{
    "application": {"max_size_mb": 150, "max_age_days": 10, "pattern": "*.log"},
    "database": {"max_size_mb": 400, "max_age_days": 21, "pattern": "*.log"},
    "monitoring": {"max_size_mb": 75, "max_age_days": 5, "pattern": "*.out"}
}
EOF

# Use custom config
python3 src/log_rotator/core.py --parent-dir /opt/logs --config-file my_log_config.json
```

## 🎯 Use Cases

### Perfect For:

- **Multi-service Applications** with logs scattered across directories
- **Microservices Architecture** with service-specific log directories
- **Legacy Systems** with inconsistent log organization
- **Development Environments** with various application logs
- **Production Systems** requiring automated log maintenance
- **Compliance Requirements** with specific retention policies

### Real-world Scenarios:

1. **E-commerce Platform**: API logs, payment logs, user activity logs in separate directories
2. **Data Pipeline**: ETL logs, database logs, scheduler logs with different retention needs
3. **DevOps Environment**: Application logs, monitoring logs, CI/CD logs with varied patterns
4. **Enterprise Systems**: Multiple application logs with department-specific policies

## 📧 Email Notifications

### Sample Email Content

You'll receive professional HTML emails with:

- **Status Header**: Color-coded (Green/Yellow/Red) status indication
- **Summary Statistics**: Files processed, space freed, directories managed
- **Alert Messages**: Important issues requiring attention
- **Detailed Breakdown**: Per-directory statistics and actions taken
- **Execution Info**: Timestamp, duration, and configuration used

### Email Triggers

- **Success**: Regular completion summary (can be disabled)
- **Warnings**: High disk usage, large cleanups, configuration issues  
- **Errors**: Task failures, permission problems, system issues
- **SLA Breaches**: When tasks exceed 30-minute SLA

## 🐛 Troubleshooting

### Common Issues

#### 1. DAG Not Appearing in Airflow UI

```bash
# Check DAG syntax
python3 $AIRFLOW_HOME/dags/log_management_dag.py

# Check Airflow scheduler logs
tail -f $AIRFLOW_HOME/logs/scheduler/latest/log

# Refresh DAGs
airflow dags reserialize
```

#### 2. Email Notifications Not Working

```bash
# Test SMTP configuration
python3 -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your-email@company.com', 'app-password')
print('SMTP connection successful!')
server.quit()
"

# Check Airflow email settings
airflow config get-value email email_backend
```

#### 3. Permission Denied Errors

```bash
# Check file permissions
ls -la /var/log/

# Fix permissions (run as appropriate user)
sudo chown -R airflow:airflow /var/log/your-logs/
sudo chmod -R 755 /var/log/your-logs/
```

#### 4. Task Failures

```bash
# Check specific task logs
airflow tasks log advanced_log_management TASK_NAME DATE 1

# Test task in isolation
airflow tasks test advanced_log_management TASK_NAME 2024-01-01

# Check system resources
df -h /var/log
free -h
```

### Debug Mode

```bash
# Run with verbose logging
python3 src/log_rotator/core.py --parent-dir /var/log --report --verbose

# Enable Airflow debug logging
export AIRFLOW__LOGGING__LOGGING_LEVEL=DEBUG
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/py-log-rotator.git
cd py-log-rotator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python3 -m pytest tests/
```

### Reporting Issues

Please use the [GitHub Issues](https://github.com/yourusername/py-log-rotator/issues) page to report bugs or request features.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Apache Airflow community for the excellent orchestration platform
- Python logging community for inspiration and best practices
- Contributors and users who help improve this project

## 📞 Support

- 📖 **Documentation**: Check our [Wiki](https://github.com/yourusername/py-log-rotator/wiki)
- 💬 **Discussions**: Join our [GitHub Discussions](https://github.com/yourusername/py-log-rotator/discussions)  
- 🐛 **Issues**: Report bugs on [GitHub Issues](https://github.com/yourusername/py-log-rotator/issues)
- 📧 **Email**: Contact the maintainer at your-email@company.com

---

⭐ **If this project helps you, please give it a star on GitHub!** ⭐