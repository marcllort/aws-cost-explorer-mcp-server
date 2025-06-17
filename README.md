# Autocost Controller

**Multi-cloud cost analysis and optimization platform with MCP (Model Context Protocol) integration.**

Autocost Controller provides powerful cost analysis tools for AWS (with GCP and Azure coming soon) through a modern MCP server that integrates seamlessly with Claude Desktop and other MCP-compatible tools.

## ✨ Features

### 🔶 AWS Cost Explorer Integration
- **Cost Analysis**: Detailed breakdowns by service, account, region, and time period
- **Dimension Discovery**: Explore all available cost dimensions and filters
- **Tag Analysis**: Analyze costs by custom tags and resource tagging strategies
- **Performance Metrics**: EC2 performance insights with cost correlation
- **Optimization Recommendations**: AI-powered cost optimization suggestions

### 🎯 Multi-Provider Architecture
- **Modular Design**: Enable/disable providers based on your needs
- **Environment-Based Configuration**: Control which providers are active
- **Unified Interface**: Consistent tool naming and behavior across providers

### 🖥️ Claude Desktop Integration
- **Multiple Configurations**: Separate endpoints for different providers
- **Environment Variables**: Clean configuration without hardcoded values
- **Auto-Discovery**: Automatically detects and configures Claude Desktop

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- AWS CLI configured (for AWS features)
- Claude Desktop (optional, for GUI integration)

### Installation & Setup

Run the interactive setup script:

```bash
python start.py
```

This guided setup will:
1. **Install dependencies** - All required Python packages
2. **Configure providers** - AWS, GCP, Azure (as available)
3. **Set up authentication** - Configurable auth methods (no hardcoded roles!)
4. **Configure Claude Desktop** - Multiple endpoint configurations
5. **Test everything** - Verify all components are working

The setup script is fully configurable and will ask you about:
- Which cloud providers to enable
- Your preferred AWS authentication method (profiles, roles, environment variables)
- Whether to configure Claude Desktop integration
- Whether to install Cursor integration

### Manual Setup (Alternative)

If you prefer manual setup:

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure AWS credentials** (choose one method):
   - **AWS Profile**: `aws configure`
   - **Environment Variables**: Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
   - **IAM Roles**: Configure role assumption (SAML, cross-account, etc.)

3. **Save credentials for Claude Desktop:**
   ```bash
   # After authenticating to AWS
   python save_credentials.py
   ```

4. **Test the setup:**
   ```bash
   python server_manual.py --test
   ```

## 🔧 Configuration

### Environment Variables

Control provider configuration with environment variables:

```bash
# Enable specific providers (comma-separated)
export AUTOCOST_PROVIDERS="aws"           # AWS only
export AUTOCOST_PROVIDERS="aws,gcp"       # AWS + GCP (when available)

# Set endpoint identifier
export AUTOCOST_ENDPOINT="aws"            # or "unified", "gcp", etc.

# Enable/disable custom company-specific tools (default: true)
export AUTOCOST_ENABLE_CUSTOM_TOOLS="true"   # Enable advanced cost analysis tools
export AUTOCOST_ENABLE_CUSTOM_TOOLS="false"  # Disable custom tools (basic tools only)
```

### Claude Desktop Configurations

The setup script creates multiple configurations in Claude Desktop:

- **`autocost-aws`**: AWS-only cost analysis
- **`autocost-unified`**: Multi-provider analysis (when multiple providers enabled)

Each configuration is automatically optimized for its specific use case.

## 🔑 Authentication

### AWS Authentication Methods

Autocost Controller supports multiple AWS authentication methods:

#### 1. AWS Profiles
```bash
aws configure --profile your-profile
export AWS_PROFILE=your-profile
```

#### 2. Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_SESSION_TOKEN=your-session-token  # if using temporary credentials
```

#### 3. Role Assumption
For SAML, OIDC, or cross-account access:
```bash
# Example with saml2aws
saml2aws login --profile your-profile

# Example with AWS CLI role assumption
aws sts assume-role --role-arn arn:aws:iam::123456789012:role/YourRole --role-session-name session
```

#### 4. Credential Saving for Claude Desktop
After authenticating with any method:
```bash
python save_credentials.py
```

This securely saves your current credentials for Claude Desktop to use.

### Required AWS Permissions

Your AWS user/role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetDimensionValues",
        "ce:GetReservationCoverage",
        "ce:GetReservationPurchaseRecommendation",
        "ce:GetReservationUtilization",
        "ce:GetUsageReport",
        "cloudwatch:GetMetricStatistics",
        "cloudwatch:ListMetrics",
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceTypes",
        "ec2:DescribeRegions",
        "ecs:ListClusters",
        "ecs:ListServices",
        "ecs:DescribeServices",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

## 🛠️ Usage

### Direct MCP Server

Run the MCP server directly:

```bash
# Start server with environment-based configuration
python server_manual.py

# Test setup and credentials
python server_manual.py --test

# Show help
python server_manual.py --help
```

### Claude Desktop Integration

After running `python start.py` and configuring Claude Desktop:

1. **Restart Claude Desktop**
2. **Select your Autocost Controller endpoint** from the tools menu
3. **Use natural language** to analyze costs:
   - "Show me AWS costs for the last 7 days"
   - "Which services are costing the most this month?"
   - "Analyze costs by environment tag"
   - "Get performance insights for EC2 instances"
   - "Run a 28-day rolling average analysis"
   - "Analyze ECS costs with Container Insights impact"
   - "Detect tenant anomalies in the last week"

### Environment Configuration

Set these environment variables to customize behavior:

```bash
# Enable/disable company-specific tools (default: true)
export AUTOCOST_ENABLE_CUSTOM_TOOLS=true

# Configure enabled providers (default: all available)
export AUTOCOST_PROVIDERS=aws,gcp,azure

# Set endpoint identifier for multi-endpoint setups
export AUTOCOST_ENDPOINT=production
```

### AWS Profile Switching

**New Feature**: Switch between AWS profiles dynamically to access different permission levels.

#### Why Use Profile Switching?
- **EC2/ECS Insights**: Performance insights require broader permissions (EC2:DescribeInstances, CloudWatch, etc.)
- **Cross-Account Analysis**: Switch between profiles for different AWS accounts
- **Role-Based Access**: Use different profiles for different permission levels

#### Quick Commands
```bash
# List available profiles
aws_profile_list()

# Switch to admin profile for enhanced insights
aws_profile_switch('admin-profile')

# Test current permissions
aws_test_permissions()

# Get EC2 performance insights (requires enhanced permissions)
aws_performance_ec2_insights(days=7)

# Switch back to limited profile
aws_profile_reset()
```

#### Typical Workflow
1. Start with basic cost analysis (limited permissions)
2. Check available profiles: `aws_profile_list()`
3. Switch to admin profile: `aws_profile_switch('admin-profile')`
4. Run enhanced analysis: `aws_performance_ec2_insights()`
5. Switch back: `aws_profile_reset()`

See **[AWS_PROFILE_SWITCHING.md](AWS_PROFILE_SWITCHING.md)** for detailed guide.

### Available Tools

The MCP server provides these tools through Claude Desktop:

#### Core Tools
- **`get_provider_status`**: Check status of all configured providers
- **`ping_server`**: Test server connectivity and basic AWS access

#### AWS Profile Management
- **`aws_profile_list`**: List all available AWS profiles
- **`aws_profile_switch`**: Switch to a different AWS profile  
- **`aws_profile_info`**: Get detailed information about a profile
- **`aws_profile_reset`**: Reset to default AWS credentials
- **`aws_test_permissions`**: Test current profile's AWS service permissions

#### AWS Cost Explorer Tools
- **`aws_cost_explorer_discover_dimensions`**: Discover available cost dimensions
- **`aws_cost_explorer_analyze_by_service`**: Quick service cost breakdown
- **`aws_cost_explorer_analyze_by_dimension`**: Analyze costs by any dimension
- **`aws_cost_explorer_list_tag_keys`**: List available tag keys for analysis
- **`aws_cost_explorer_analyze_by_custom_tag`**: Analyze costs by specific tags
- **`aws_cost_explorer_analyze_by_name_tag`**: Analyze costs by Name tag values
- **`aws_cost_explorer_analyze_specific_resource`**: Detailed analysis for a specific resource

#### AWS Performance Tools
- **`aws_performance_ec2_insights`**: EC2 performance metrics with cost correlation *(requires enhanced permissions)*
- **`get_ecs_performance_insights`**: ECS performance analysis *(requires enhanced permissions)*  
- **`get_cost_optimization_recommendations`**: AI-powered optimization suggestions

#### AWS Advanced Cost Analysis
- **`aws_rolling_average_analysis`**: 28-day rolling average cost analysis with trend detection
- **`aws_ecs_cost_deep_dive`**: Detailed ECS cost breakdown (Fargate vs EC2, Container Insights impact)
- **`aws_spot_instance_cost_impact`**: Spot vs On-Demand analysis with volatility tracking
- **`aws_savings_plan_utilization_analysis`**: Savings Plan efficiency and waste detection
- **`aws_tenant_cost_analysis`**: Cost breakdown by organization/tenant with anomaly detection
- **`aws_redshift_cost_analysis`**: Cluster-by-cluster Redshift cost analysis
- **`aws_spot_capacity_impact_analysis`**: Spot capacity constraints and Savings Plan spillover analysis
- **`aws_container_insights_cost_analysis`**: Container Insights monitoring costs and ROI analysis
- **`aws_cross_service_impact_analysis`**: Track cascading cost impacts across services
- **`aws_savings_plan_spillover_analysis`**: Analyze spillover when spot unavailability forces SP consumption
- **`aws_instance_type_capacity_strategy`**: Instance type diversification and capacity planning recommendations

#### Company-Specific Tools *(Optional - Enable via `AUTOCOST_ENABLE_CUSTOM_TOOLS=true`)*
- **`aws_tenant_anomaly_detector`**: Detect unusual tenant spending patterns with baseline comparison
- **`aws_uat_environment_cost_monitor`**: Monitor UAT vs Production cost ratios and identify optimization opportunities

## 📁 Project Structure

```
autocost_controller/
├── core/                    # Core configuration and logging
├── providers/               # Cloud provider implementations
│   ├── aws/                # AWS provider
│   └── manager.py          # Provider management
├── tools/                   # MCP tool implementations
│   ├── __init__.py         # Core tools registration
│   ├── aws_tools.py        # AWS cost analysis tools
│   └── aws_performance.py  # AWS performance tools
├── server_manual.py         # MCP server (environment-aware)
├── save_credentials.py      # Credential management utility
├── start.py                # Interactive setup script
└── README.md               # This file
```

## 🔒 Security

- **Credentials are stored securely** with restrictive file permissions (600)
- **No hardcoded secrets** - all authentication is configurable
- **Environment-based configuration** - no sensitive data in code
- **Read-only permissions** - tools only read cost/performance data

## 🚨 Troubleshooting

### AWS Authentication Issues

1. **Check credential status:**
   ```bash
   python save_credentials.py --status
   ```

2. **Test AWS connectivity:**
   ```bash
   aws sts get-caller-identity
   ```

3. **Verify saved credentials:**
   ```bash
   python server_manual.py --test
   ```

### Claude Desktop Issues

1. **Restart Claude Desktop** after configuration changes
2. **Check configuration file** location:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/claude/claude_desktop_config.json`
   - Windows: `~/AppData/Roaming/Claude/claude_desktop_config.json`

3. **Verify MCP server logs** in Claude Desktop's developer tools

### Provider Status Issues

```bash
# Check which providers are ready
python server_manual.py --test

# Verify environment variables
echo $AUTOCOST_PROVIDERS
echo $AUTOCOST_ENDPOINT
```

## 🗺️ Roadmap

- **✅ AWS Cost Explorer** - Complete with advanced analytics
- **✅ Multi-provider architecture** - Extensible foundation
- **🔄 GCP Cost Management** - In development
- **🔄 Azure Cost Management** - In development
- **🔄 Cross-cloud cost comparison** - Planned
- **🔄 Advanced optimization recommendations** - AI-powered insights

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 💡 Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: This README and inline code documentation
- **Setup Script**: Run `python start.py` for guided setup assistance

---

**Autocost Controller** - Bringing powerful cloud cost analysis to your development workflow through Claude Desktop and MCP integration.
