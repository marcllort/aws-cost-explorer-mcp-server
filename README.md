# 🚀 Autocost Controller

A powerful **multi-cloud cost optimization platform** with **MCP (Model Context Protocol)** integration, designed to provide AI-powered cost analysis and optimization recommendations across AWS, GCP, Azure, and DataDog.

## ✨ Features

- 🔍 **Multi-provider cost analysis** (AWS, GCP, Azure, DataDog)
- 📊 **Performance insights** and optimization recommendations  
- 🤖 **Claude Desktop & Cursor integration** via MCP
- 🏷️ **Advanced tagging** and cost allocation
- 💡 **AI-powered optimization** suggestions
- 🔧 **One-command setup** with automatic credential capture
- 🎯 **Provider-specific endpoints** for focused analysis

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- AWS CLI configured (for AWS features)
- DataDog API keys (for DataDog features)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd aws-cost-explorer-mcp-server
python start.py
```

That's it! The `start.py` script will:
- ✅ Install all dependencies automatically
- ✅ Capture your current AWS credentials
- ✅ Verify your setup
- ✅ Guide you through any missing configuration

### 2. Start the Server
```bash
python start.py --server
```

### 3. Full Configuration (if needed)
```bash
python start.py --configure
```

## 📋 Command Reference

| Command | Description |
|---------|-------------|
| `python start.py` | **Default**: Capture credentials + verify setup |
| `python start.py --server` | Start the MCP server |
| `python start.py --configure` | Run full configuration wizard |
| `python start.py --verify` | Verify current setup |
| `python start.py --help` | Show usage information |

## 🔧 Configuration

### AWS Setup
The system supports multiple AWS authentication methods:

#### Method 1: AWS SSO (Recommended)
```bash
aws sso login
python start.py  # Automatically captures credentials
```

#### Method 2: AWS Profiles
```bash
aws configure --profile your-profile
export AWS_PROFILE=your-profile
python start.py
```

#### Method 3: Assumed Roles
```bash
# Run your assume role command
aws sts assume-role --role-arn arn:aws:iam::ACCOUNT:role/ROLE --role-session-name session
python start.py  # Captures session credentials automatically
```

### DataDog Setup
```bash
export DATADOG_API_KEY=your-api-key
export DATADOG_APP_KEY=your-app-key
export DATADOG_SITE=datadoghq.com  # Optional, defaults to datadoghq.com
python start.py --configure
```

## 🔌 IDE Integration

### Claude Desktop
The setup script automatically configures Claude Desktop:

1. Run `python start.py --configure`
2. Choose "Auto-install for Claude Desktop"
3. Restart Claude Desktop
4. Your cost analysis tools will be available

### Cursor
For Cursor integration:

1. Run `python start.py --configure` 
2. Choose "Auto-install for Cursor"
3. Restart Cursor
4. Tools available in MCP server list

## 🛠️ Available Tools

### AWS Cost Analysis
- `aws_cost_explorer_analyze_costs` - Comprehensive cost analysis
- `aws_cost_explorer_analyze_by_service` - Service-level cost breakdown
- `aws_cost_explorer_analyze_by_name_tag` - Tag-based cost allocation
- `aws_performance_ec2_insights` - EC2 performance and optimization
- `aws_performance_ecs_insights` - ECS performance analysis
- `aws_cost_optimization_recommendations` - AI-powered optimization suggestions

### AWS Profile Management
- `aws_profile_list` - List available AWS profiles
- `aws_profile_switch` - Switch between profiles
- `aws_profile_info` - Get profile details
- `aws_test_permissions` - Test current permissions
- `aws_refresh_credentials` - Refresh credentials from environment

### DataDog Monitoring
- `datadog_logs_search` - Search and analyze logs
- `datadog_metrics_query` - Query metrics with filtering
- `datadog_dashboards_list` - List available dashboards
- `datadog_usage_analysis` - Usage and cost analysis
- `datadog_test_connection` - Test connection and authentication

### System Tools
- `get_provider_status` - Check all provider statuses
- `ping_server` - Test server connectivity

## 🔍 Usage Examples

### Basic Cost Analysis
```python
# Analyze AWS costs for the last 30 days
aws_cost_explorer_analyze_costs(days=30)

# Break down costs by service
aws_cost_explorer_analyze_by_service(days=7)

# Analyze costs by Name tag
aws_cost_explorer_analyze_by_name_tag(days=14)
```

### Performance Optimization
```python
# Get EC2 performance insights
aws_performance_ec2_insights(days=7)

# Get optimization recommendations
aws_cost_optimization_recommendations(days=30)
```

### DataDog Analysis
```python
# Search recent logs
datadog_logs_search(query="ERROR", hours=24)

# Query custom metrics
datadog_metrics_query(metric="custom.app.latency", hours=6)

# Analyze DataDog usage costs
datadog_usage_analysis(days=30)
```

### Profile Management
```python
# List available AWS profiles
aws_profile_list()

# Switch to admin profile for detailed analysis
aws_profile_switch("admin-profile")

# Test current permissions
aws_test_permissions()
```

## 🏗️ Architecture

### Provider System
Each cloud provider is implemented as a separate module:

```
autocost_controller/
├── providers/
│   ├── aws/           # AWS Cost Explorer & Performance
│   ├── gcp/           # Google Cloud (coming soon)
│   ├── azure/         # Microsoft Azure (coming soon)
│   └── datadog/       # DataDog monitoring
├── tools/             # MCP tools
└── core/              # Core framework
```

### Configuration Management
- **Environment variables**: Stored in `.env`
- **Endpoint configs**: JSON files in `configs/` 
- **Credentials**: Automatically captured and stored securely
- **MCP integration**: Auto-configured for Claude Desktop & Cursor

## 🔐 Security & Credentials

### AWS Credentials
- **Automatic capture**: From current session/environment
- **Multiple auth methods**: SSO, profiles, assumed roles
- **Session token support**: For temporary credentials
- **Secure storage**: Local credential files for MCP server

### DataDog Credentials
- **API/App keys**: Stored in environment variables
- **Connection testing**: Validates permissions before saving
- **Site configuration**: Supports different DataDog sites

### Best Practices
- ✅ Use least-privilege access
- ✅ Rotate credentials regularly
- ✅ Store sensitive data in environment variables
- ✅ Test permissions before analysis

## 🚨 Troubleshooting

### Common Issues

#### "ExpiredToken" Error
```bash
# Refresh your AWS session
aws sso login  # or re-run assume role command
python start.py  # Re-capture credentials
```

#### "No providers configured"
```bash
python start.py --configure  # Run full setup
```

#### "Permission denied" for EC2 insights
```bash
aws_profile_list()  # Check available profiles
aws_profile_switch("admin-profile")  # Switch to profile with EC2 permissions
```

#### DataDog connection fails
```bash
# Verify your credentials
python start.py --verify
# Update credentials if needed
python start.py --configure
```

### Verification Commands
```bash
# Check overall setup
python start.py --verify

# Test AWS credentials
aws sts get-caller-identity

# Test DataDog credentials (if configured)
datadog_test_connection()
```

## 🧪 Development

### Adding New Providers
See the [Provider Development Guide](PROVIDER_DEVELOPMENT.md) for detailed instructions on implementing new cloud providers.

### Project Structure
```
├── start.py                    # Single entry point for all operations (setup, server, verification)
├── autocost_controller/        
│   ├── providers/              # Provider implementations
│   ├── tools/                  # MCP tools
│   ├── core/                   # Core framework
│   └── utils/                  # Shared utilities
├── configs/                    # Endpoint configurations
└── .env                        # Environment variables
```

### Key Dependencies
- **boto3**: AWS SDK
- **datadog-api-client**: DataDog API
- **mcp**: Model Context Protocol
- **rich**: Beautiful terminal interface
- **pydantic**: Data validation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the provider development guide for new integrations
4. Add tests for new functionality
5. Update documentation
6. Submit a pull request

## 📄 License

[Your License Here]

## 🆘 Support

- **Issues**: [GitHub Issues](link-to-issues)
- **Documentation**: [Wiki](link-to-wiki) 
- **Discussions**: [GitHub Discussions](link-to-discussions)

---

**Made with ❤️ for cloud cost optimization**
