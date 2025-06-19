"""
GCP tools registration for Autocost Controller.

🚨 CRITICAL GUIDELINES FOR LLMs USING THESE TOOLS:

RESOURCE CREATION SAFETY:
- NEVER automatically create resources without explicit user confirmation
- ALWAYS call configuration/review tools with confirmed=false FIRST
- STOP and wait for user to explicitly say "yes, create it" or similar
- DO NOT assume user consent based on their initial request
- Treat every resource creation as requiring explicit approval

SHOWING TOOL RESPONSES:
- ALWAYS show the complete response from tools to the user
- Do NOT just reference that you called a tool - show the actual output
- Tool responses contain important information users need to see
- Educational content, status updates, and instructions must be displayed

CONFIRMATION PATTERN:
1. Show configuration review (confirmed=false)
2. STOP and ask user for explicit confirmation
3. Wait for user to say "yes, proceed" or similar
4. Only then call with confirmed=true

EXAMPLES OF WHAT NOT TO DO:
❌ "Since you want billing data, let me create the dataset"
❌ Automatically calling tools with confirmed=true
❌ Assuming user wants resources created
❌ Hiding tool responses from users

EXAMPLES OF CORRECT BEHAVIOR:
✅ "Here's what would be created. Do you want to proceed?"
✅ "Please review and confirm if you want me to create these resources"
✅ Waiting for explicit user approval before any resource creation
✅ Showing complete tool responses to users
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, List, Optional
from ..core.provider_manager import ProviderManager
from ..core.config import Config
from ..core.logger import AutocostLogger
from .gcp_cost_analysis import register_gcp_cost_analysis_tools
from .gcp_performance import register_gcp_performance_tools


def register_gcp_tools(mcp, provider_manager: ProviderManager, 
                      config: Config, logger: AutocostLogger) -> None:
    """Register all GCP tools."""
    
    gcp_provider = provider_manager.get_provider("gcp")
    if not gcp_provider:
        logger.warning("GCP provider not available, skipping tools registration")
        return
    
    # Register cost analysis tools
    register_gcp_cost_analysis_tools(mcp, provider_manager, config, logger)
    
    # Register performance tools
    register_gcp_performance_tools(mcp, provider_manager, config, logger)
    
    # Register GCP-specific tools
    
    @mcp.tool()
    async def gcp_test_permissions(random_string: str = "") -> str:
        """Test GCP permissions for various services with current project."""
        logger.info("🔍 Testing GCP permissions...")
        
        try:
            # Test basic connectivity
            if not await gcp_provider.test_connection():
                return "❌ Failed to connect to GCP"
            
            # Get current project info
            project_info = gcp_provider.get_project_info()
            if not project_info:
                return "❌ Failed to get project information"
            
            # Test various services
            services_status = []
            
            # Test Billing API
            try:
                client = gcp_provider.get_client('billing')
                services_status.append("✅ Billing API")
            except Exception as e:
                services_status.append(f"❌ Billing API: {str(e)}")
            
            # Test Monitoring API
            try:
                client = gcp_provider.get_client('monitoring')
                services_status.append("✅ Monitoring API")
            except Exception as e:
                services_status.append(f"❌ Monitoring API: {str(e)}")
            
            # Test Resource Manager API
            try:
                client = gcp_provider.get_client('resource_manager')
                services_status.append("✅ Resource Manager API")
            except Exception as e:
                services_status.append(f"❌ Resource Manager API: {str(e)}")
            
            # Generate report
            report = f"""
            GCP Permissions Test Results:
            
            🔑 Authentication:
            - Project: {project_info.get('project_id', 'Unknown')}
            - Name: {project_info.get('name', 'Unknown')}
            - Number: {project_info.get('number', 'Unknown')}
            - State: {project_info.get('state', 'Unknown')}
            
            🔌 API Access:
            """
            
            for status in services_status:
                report += f"- {status}\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to test GCP permissions: {str(e)}", "gcp")
            return f"Error testing GCP permissions: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_list(random_string: str = "") -> str:
        """List all available GCP projects (fast - IDs only)."""
        logger.info("🔍 Listing GCP projects...")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Fast listing - just project IDs
            report = f"""📋 **Available GCP Projects**
Organization: {gcp_provider.get_organization_id() or 'N/A'}
Total Projects: {len(projects)}

🚀 **Quick List** (Project IDs):
"""
            
            # Show projects in columns for better readability
            for i, project in enumerate(projects, 1):
                if i <= 50:  # Show first 50 projects
                    report += f"{i:3d}. {project}\n"
                elif i == 51:
                    report += f"\n... and {len(projects) - 50} more projects\n"
                    break
            
            report += f"""
💡 **Usage Tips**:
• Use gcp_project_info("project-id") for detailed info about a specific project
• Use gcp_project_switch("project-id") to switch to a different project
• Use gcp_project_list_detailed() for detailed info (slower for large lists)

📊 **Summary**: {len(projects)} projects accessible under organization {gcp_provider.get_organization_id() or 'N/A'}
"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to list GCP projects: {str(e)}", "gcp")
            return f"Error listing GCP projects: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_list_detailed(limit: int = 20, random_string: str = "") -> str:
        """List GCP projects with detailed information (slower - use limit to control performance)."""
        logger.info(f"🔍 Listing GCP projects with details (limit: {limit})...")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Limit the number of projects to fetch details for
            limited_projects = projects[:limit]
            
            report = f"""📋 **Detailed GCP Projects List**
Organization: {gcp_provider.get_organization_id() or 'N/A'}
Total Projects: {len(projects)}
Showing Details: {len(limited_projects)} projects

🔍 **Detailed Information**:
"""
            
            for i, project in enumerate(limited_projects, 1):
                try:
                    info = gcp_provider.get_project_info(project)
                    if info:
                        report += f"\n{i:2d}. **{info['name']}** ({info['project_id']})\n"
                        report += f"    State: {info['state']}\n"
                        report += f"    Number: {info['number']}\n"
                        if info.get('labels'):
                            labels = ', '.join(f'{k}={v}' for k, v in list(info['labels'].items())[:3])
                            report += f"    Labels: {labels}\n"
                    else:
                        report += f"\n{i:2d}. **{project}** (Error getting details)\n"
                except Exception as e:
                    report += f"\n{i:2d}. **{project}** (Error: {str(e)[:50]}...)\n"
            
            if len(projects) > limit:
                report += f"\n... and {len(projects) - limit} more projects (use gcp_project_list() for full list)\n"
            
            report += f"""
💡 **Performance Tips**:
• Use gcp_project_list() for fast ID-only listing
• Increase limit parameter for more detailed results (slower)
• Use gcp_project_info("specific-id") for single project details

📊 **Summary**: Showed {len(limited_projects)} of {len(projects)} total projects
"""
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to list GCP projects with details: {str(e)}", "gcp")
            return f"Error listing GCP projects with details: {str(e)}"
    
    @mcp.tool()
    async def gcp_project_activity_check(limit: int = 30, days: int = 30, random_string: str = "") -> str:
        """Check recent activity for GCP projects to see when they were last used.
        
        ⚠️ PERFORMANCE WARNING: This function can be slow (~2 seconds per project).
        With default limit=30, expect ~60 seconds total execution time.
        Consider using a smaller limit (e.g., 10) for faster results.
        """
        logger.info(f"🔍 Checking activity for {limit} GCP projects over last {days} days...")
        logger.info(f"⚠️ This may take ~{limit * 2} seconds to complete ({limit} projects × ~2s each)")
        
        try:
            projects = gcp_provider.list_available_projects()
            
            if not projects:
                return "No GCP projects found or insufficient permissions"
            
            # Limit the number of projects to check for performance
            limited_projects = projects[:limit]
            
            active_projects = []
            inactive_projects = []
            error_projects = []
            
            logger.info(f"📊 Analyzing {len(limited_projects)} projects...")
            
            for i, project_id in enumerate(limited_projects, 1):
                try:
                    # Get project info
                    info = gcp_provider.get_project_info(project_id)
                    
                    if not info:
                        error_projects.append((project_id, "Failed to get info"))
                        continue
                    
                    # Check project state
                    state = info.get('state', 'Unknown')
                    name = info.get('name', 'Unknown')
                    create_time = info.get('create_time')
                    
                    if state != 'ACTIVE':
                        inactive_projects.append((project_id, name, f"State: {state}"))
                        continue
                    
                    # For active projects, categorize by naming patterns
                    # This is a heuristic since we don't have usage metrics easily available
                    
                    # Check if it's a system project (usually auto-generated)
                    if project_id.startswith('sys-'):
                        inactive_projects.append((project_id, name, "System project (likely auto-generated)"))
                    elif any(keyword in project_id.lower() for keyword in ['test', 'demo', 'staging']):
                        active_projects.append((project_id, name, "Development/Test project"))
                    elif any(keyword in project_id.lower() for keyword in ['cosmos', 'scheduling', 'nuvolar', 'couplesync']):
                        active_projects.append((project_id, name, "Application project"))
                    else:
                        active_projects.append((project_id, name, "Active project"))
                        
                except Exception as e:
                    error_projects.append((project_id, str(e)[:50]))
            
            # Build results
            report = []
            report.append(f"📊 **GCP Project Activity Analysis**")
            report.append(f"Organization: {gcp_provider.get_organization_id()}")
            report.append(f"Analyzed: {len(limited_projects)} of {len(projects)} total projects")
            report.append("")
            
            if active_projects:
                report.append(f"✅ **Likely Active Projects** ({len(active_projects)}):")
                for project_id, name, category in active_projects:
                    report.append(f"  • {name} ({project_id})")
                    report.append(f"    Category: {category}")
                report.append("")
            
            if inactive_projects:
                report.append(f"⏸️ **Likely Inactive Projects** ({len(inactive_projects)}):")
                for project_id, name, status in inactive_projects[:10]:
                    report.append(f"  • {name} ({project_id})")
                    report.append(f"    Status: {status}")
                if len(inactive_projects) > 10:
                    report.append(f"  ... and {len(inactive_projects) - 10} more")
                report.append("")
            
            if error_projects:
                report.append(f"❌ **Errors** ({len(error_projects)}):")
                for project_id, error in error_projects[:5]:
                    report.append(f"  • {project_id}: {error}")
                report.append("")
            
            report.append(f"📊 **Summary:**")
            report.append(f"• Likely Active: {len(active_projects)} projects")
            report.append(f"• Likely Inactive: {len(inactive_projects)} projects")
            report.append(f"• Errors: {len(error_projects)} projects")
            report.append("")
            report.append(f"💡 **Note:** This analysis is based on project names, states, and patterns.")
            report.append(f"For detailed usage metrics, billing data or monitoring APIs would be needed.")
            
            logger.cost_analysis_summary("gcp", len(active_projects), days, len(limited_projects))
            return "\n".join(report)
            
        except Exception as e:
            error_msg = f"❌ Error checking project activity: {str(e)}"
            logger.error(error_msg, "gcp")
            return error_msg
    
    @mcp.tool()
    async def gcp_project_switch(project_id: str) -> str:
        """Switch to a different GCP project."""
        logger.info(f"🔄 Switching to GCP project: {project_id}")
        
        try:
            if gcp_provider.set_project(project_id):
                info = gcp_provider.get_project_info(project_id)
                
                return f"""
                ✅ Successfully switched to GCP project:
                - Project ID: {info['project_id']}
                - Name: {info['name']}
                - Number: {info['number']}
                - State: {info['state']}
                """
            else:
                return f"❌ Failed to switch to project: {project_id}"
            
        except Exception as e:
            logger.error(f"Failed to switch GCP project: {str(e)}", "gcp")
            return f"Error switching GCP project: {str(e)}"
    
    @mcp.tool()
    async def gcp_setup_billing_export(
        random_string: str = ""
    ) -> str:
        """
        🎯 GCP Billing Export Setup Guide: Complete setup for detailed cost analysis.
        
        This interactive tool guides you through setting up BigQuery billing export,
        which is essential for comprehensive cost analysis and optimization.
        
        🚨 FOR LLMs: ALWAYS show the complete response from this tool to the user.
        This contains important educational information and setup guidance that the user needs to see.
        """
        logger.info("🎯 Starting comprehensive GCP billing export setup guide...")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        try:
            # Step 1: Explain the importance and benefits
            explanation = """
🎯 **Why Do You Need BigQuery Billing Export?**

To provide you with comprehensive cost analysis, optimization recommendations, and detailed insights, 
we need access to your complete billing data. Here's what this enables:

📊 **Enhanced Analytics:**
• Detailed cost breakdowns by service, project, and resource
• Historical trend analysis and forecasting
• Resource-level cost attribution (which VM costs what)
• Label-based cost allocation and chargeback

💡 **Smart Recommendations:**
• Identify underutilized resources for cost savings
• Committed Use Discount (CUD) optimization opportunities
• Right-sizing recommendations for VMs and other resources
• Detect cost anomalies and spending spikes

🔍 **Advanced Features:**
• Cross-project cost analysis and comparisons
• Custom cost reporting and dashboards
• Integration with FinOps best practices
• Automated cost alerts and budgeting

⚡ **What Gets Exported:**
• Standard usage cost data: Basic cost and usage information
• Detailed usage cost data: Resource-level granular data
• Pricing data: Current pricing information for all services

💰 **Cost Impact:**
• BigQuery storage and querying costs are minimal (typically <$10/month)
• Data loading is free, querying costs depend on analysis frequency
• The cost savings from insights typically far exceed the storage costs

---
"""

            # Step 2: Check current status
            logger.info("🔍 Checking current billing export status...")
            
            # Get billing account info
            try:
                billing_info = await gcp_provider.get_billing_account_info()
                if not billing_info.get('billing_accounts'):
                    return explanation + "\n❌ No billing accounts found. Please ensure you have billing account access."
                
                primary_account = billing_info['billing_accounts'][0]
                account_name = primary_account.get('displayName', 'Unknown')
                account_id = primary_account.get('name', '').split('/')[-1] if primary_account.get('name') else 'Unknown'
                
                status_info = f"""
📋 **Current Setup Status:**
• Billing Account: {account_name} ({account_id})
• Current Project: {gcp_provider.get_current_project()}
"""
            except Exception as e:
                status_info = f"""
📋 **Current Setup Status:**
• Current Project: {gcp_provider.get_current_project()}
• Note: Could not retrieve billing account info ({str(e)})
"""

            # Step 3: Interactive questions and guidance
            setup_guide = """
🤔 **Before We Proceed - Quick Questions:**

1️⃣ **Do you already have BigQuery billing export enabled?**
   • Check in Google Cloud Console → Billing → Billing export
   • If you see active exports to BigQuery, you may already be set up!

2️⃣ **Do you have a preferred project for storing billing data?**
   • We recommend a dedicated "FinOps" project for billing analysis
   • This keeps billing data separate from your application projects
   • The project should be linked to the same billing account

3️⃣ **What's your preferred data location?**
   • **US (recommended)**: Best performance, retroactive data included
   • **EU**: GDPR compliance, retroactive data included  
   • **Specific regions**: Limited retroactive data, check limitations

---

🚀 **Automated Setup Options:**

We can help you with the technical setup, but the actual billing export configuration 
must be done through the Google Cloud Console (Google doesn't provide APIs for this).

**What we can do automatically:**
✅ Create and configure BigQuery dataset
✅ Set up proper permissions and labels
✅ Validate your setup and provide troubleshooting
✅ Guide you through the manual console steps

**What requires manual steps:**
⚠️ Enabling the actual billing export in Cloud Console
⚠️ Selecting which types of data to export
⚠️ Choosing the export frequency and settings

---

📝 **Ready to Proceed?**

If you'd like to continue with the setup, we'll:
1. Create a properly configured BigQuery dataset
2. Provide step-by-step instructions for the console configuration
3. Help you verify everything is working correctly

Would you like to proceed with the automated dataset setup? 
You can then follow our detailed guide for the manual console steps.

**To review what would be created (NO resources created yet), run:**
`gcp_setup_billing_export_interactive`

**To get manual setup instructions only, run:**
`gcp_billing_setup_and_cost_guide`

🚨 **Important**: The interactive tool will show you a configuration review first. 
NO resources will be created until you explicitly confirm you want to proceed.

---

💡 **Quick Start Alternative:**
If you prefer to set everything up manually, visit:
https://cloud.google.com/billing/docs/how-to/export-data-bigquery
"""

            return explanation + status_info + setup_guide

        except Exception as e:
            logger.error(f"Error in billing export setup guide: {str(e)}")
            return f"""
❌ **Error during setup guide**: {str(e)}

📚 **Manual Setup Alternative:**
If you encounter issues, you can set up billing export manually:

1. Visit Google Cloud Console → Billing → Billing export
2. Follow our comprehensive guide: Run `gcp_billing_setup_and_cost_guide`
3. Or visit: https://cloud.google.com/billing/docs/how-to/export-data-bigquery

Need help? The manual guide provides detailed troubleshooting steps.
"""

    @mcp.tool()
    async def gcp_setup_billing_export_interactive(
        dataset_id: str = "billing_export",
        location: str = "US",
        table_prefix: str = "gcp_billing_export",
        create_project: bool = False,
        project_name: str = "finops-billing-analysis",
        confirmed: bool = False
    ) -> str:
        """
        🔧 Interactive BigQuery Dataset Setup for Billing Export.
        
        Creates and configures a BigQuery dataset optimized for billing data,
        then provides detailed instructions for completing the setup in Cloud Console.
        
        🚨 CRITICAL FOR LLMs: 
        - ALWAYS call this tool with confirmed=false FIRST
        - NEVER automatically call with confirmed=true
        - MUST wait for explicit user confirmation before proceeding
        - DO NOT assume user consent - always ask explicitly
        - STOP and wait for user to say "yes, create it" or similar
        - ALWAYS show the complete response from this tool to the user
        
        Args:
            dataset_id: Name for the BigQuery dataset (default: billing_export)
            location: BigQuery dataset location - US, EU, or specific region
            table_prefix: Prefix for billing tables (default: gcp_billing_export)  
            create_project: Whether to create a new dedicated FinOps project
            project_name: Name for new project if create_project=True
            confirmed: Set to true to proceed with dataset creation (ONLY after user confirms)
        """
        logger.info(f"🔧 Interactive BigQuery billing export setup...")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        try:
            # Get current project and billing info
            current_project = gcp_provider.get_current_project()
            
            # If not confirmed, show configuration review
            if not confirmed:
                confirmation_prompt = f"""
🔧 **BigQuery Billing Export Setup - Configuration Review**

⚠️ **IMPORTANT: NO RESOURCES WILL BE CREATED YET** ⚠️

This is a configuration review. You must explicitly confirm before any BigQuery resources are created.

📋 **Proposed Configuration:**
• **Current GCP Project**: {current_project}
• **Proposed Dataset Name**: {dataset_id}
• **Proposed Location**: {location}
• **Table Prefix**: {table_prefix}
• **Create New Project**: {'Yes' if create_project else 'No'}
{f'• **New Project Name**: {project_name}' if create_project else ''}

---

📍 **Location Options & Implications:**

**Multi-Region (Recommended):**
• **US**: Best performance, includes retroactive data, lowest cost
• **EU**: GDPR compliance, includes retroactive data

**Single Regions:**
• **Americas**: us-central1, us-east1, us-east4, us-west1, us-west2, etc.
• **Europe**: europe-west1, europe-west2, europe-west3, europe-west4, etc.
• **Asia Pacific**: asia-east1, asia-northeast1, asia-southeast1, etc.

⚠️ **Important**: Single regions have limited retroactive data compared to US/EU multi-regions.

---

💰 **Cost Estimate:**
• **BigQuery Storage**: ~$0.02/GB/month (billing data typically <1GB/month)
• **Query Costs**: ~$5/TB queried (analysis typically <$5/month)
• **Data Loading**: FREE (no cost for billing export ingestion)
• **Total Estimated Cost**: $2-10/month depending on usage

---

🤔 **Before We Proceed - Please Review:**

**❓ Questions to Consider:**

1️⃣ **Dataset Name**: Is "{dataset_id}" a good name? 
   • Should be descriptive and follow your naming conventions
   • Common alternatives: "billing_data", "cost_analysis", "finops_data"

2️⃣ **Location Choice**: Is "{location}" the right location?
   • Consider data residency requirements
   • US/EU recommended for full retroactive data
   • Choose region close to your main operations

3️⃣ **Project Selection**: Should we use "{current_project}"?
   • Recommended: Use a dedicated FinOps/billing project
   • Alternative: Use current project if it's appropriate
   • Consider: Who needs access to this billing data?

4️⃣ **Table Prefix**: Is "{table_prefix}" appropriate?
   • This will be the prefix for all billing export tables
   • Example tables: {table_prefix}_20241201, {table_prefix}_20241202, etc.

---

🚨 **EXPLICIT CONFIRMATION REQUIRED** 🚨

**❌ NO RESOURCES HAVE BEEN CREATED YET**

To proceed with BigQuery dataset creation, you must:
1. **Review the configuration above carefully**
2. **Decide if you want to modify any settings**
3. **Run the command again with confirmed=true**

**⚠️ ONLY AFTER YOU CONFIRM will we create the BigQuery dataset**

**To proceed with dataset creation (AFTER reviewing), run:**
```
gcp_setup_billing_export_interactive(
    dataset_id="{dataset_id}",
    location="{location}",
    table_prefix="{table_prefix}",
    create_project={str(create_project).lower()},
    project_name="{project_name}",
    confirmed=true
)
```

🔧 **Customize settings first (if needed):**

**Different location:**
```
gcp_setup_billing_export_interactive(
    dataset_id="{dataset_id}",
    location="EU",  # or "europe-west1"
    table_prefix="{table_prefix}",
    confirmed=true
)
```

**Different dataset name:**
```
gcp_setup_billing_export_interactive(
    dataset_id="billing_data",  # or "cost_analysis"
    location="{location}",
    table_prefix="{table_prefix}",
    confirmed=true
)
```

---

💡 **Need Help Deciding?**

**Recommended Settings for Most Users:**
• **Dataset ID**: "billing_export" (standard, clear naming)
• **Location**: "US" (best performance, full retroactive data)
• **Table Prefix**: "gcp_billing_export" (follows GCP conventions)
• **Create Project**: false (use existing project initially)

**For Enterprise/Multi-Team:**
• Consider creating a dedicated FinOps project
• Use location that matches your data residency requirements
• Choose dataset name that fits your organization's naming conventions

---

🔄 **What Happens When You Confirm?**

When you run the command with confirmed=true:
1. ✅ BigQuery dataset will be created automatically
2. 📋 You'll get step-by-step Cloud Console instructions
3. ⚙️ You'll complete the billing export setup in GCP Console
4. ⏰ Wait 24-48 hours for data to start flowing
5. 📊 Use our cost analysis tools for insights!

---

🛑 **TAKE YOUR TIME TO REVIEW**

**Please:**
• **Review the configuration above carefully**
• **Consider your organization's requirements**
• **Modify settings if needed**
• **Only proceed when you're ready**

**Remember: You can always delete the dataset later if needed, but it's better to get the configuration right the first time.**

**When you're ready to proceed, run the command above with confirmed=true**
"""
                return confirmation_prompt

            # If confirmed, proceed with dataset creation
            logger.info(f"🚀 User confirmed - Creating BigQuery dataset '{dataset_id}' in location '{location}'")
            
            # Validate location
            valid_locations = [
                "US", "EU", 
                "northamerica-northeast1", "southamerica-east1", "us-central1", 
                "us-east1", "us-east4", "us-west1", "us-west2", "us-west3", "us-west4",
                "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2", 
                "asia-northeast3", "asia-south1", "asia-southeast1", "asia-southeast2", 
                "australia-southeast1", "europe-central2", "europe-north1", 
                "europe-west1", "europe-west2", "europe-west3", "europe-west4", "europe-west6"
            ]
            
            if location not in valid_locations:
                return f"""
❌ **Invalid location**: {location}

📍 **Valid BigQuery locations for billing data:**

**Multi-region (Recommended):**
• US - Best performance, includes retroactive data
• EU - GDPR compliance, includes retroactive data

**Supported Regions:**
• Americas: {', '.join([loc for loc in valid_locations if loc.startswith(('northamerica', 'southamerica', 'us-'))])}
• Asia Pacific: {', '.join([loc for loc in valid_locations if loc.startswith(('asia-', 'australia-'))])}  
• Europe: {', '.join([loc for loc in valid_locations if loc.startswith('europe-')])}

💡 **Recommendation**: Use 'US' or 'EU' for best results and retroactive data inclusion.
"""

            # Step 1: Project setup (if requested)
            project_setup_result = ""
            if create_project:
                project_setup_result = f"""
🏗️ **Project Creation Status:**
⚠️ Note: Automatic project creation requires additional permissions and setup.
For now, please create the project manually:

1. Go to Google Cloud Console → Project Selector → New Project
2. Project Name: {project_name}
3. Ensure it's linked to your billing account
4. Enable BigQuery API and BigQuery Data Transfer Service API

Once created, switch to that project and re-run this tool.

---
"""

            # Step 2: Create BigQuery dataset
            success, message = gcp_provider.setup_billing_export_with_preferences(
                dataset_id=dataset_id,
                location=location,
                table_prefix=table_prefix
            )

            if not success:
                return f"""
❌ **Dataset Creation Failed**: {message}

🔧 **Troubleshooting Steps:**
1. Ensure BigQuery API is enabled in your project
2. Verify you have BigQuery Admin permissions
3. Check that the dataset name '{dataset_id}' is valid and unique
4. Confirm the location '{location}' is supported

**Manual Alternative:**
You can create the dataset manually in BigQuery console and then run the manual setup guide.
"""

            # Step 3: Provide comprehensive setup instructions with console guidance
            billing_export_setup = f"""
✅ **Dataset Created Successfully!**
{message}

---

🎯 **Next Step: Enable Billing Export in Cloud Console**

**IMPORTANT**: The BigQuery dataset has been created, but you still need to configure 
the actual billing export through the Google Cloud Console. This cannot be automated.

**🚀 Ready for the next step?**

**Option 1: Guided Console Setup (Recommended)**
After the server is restarted with the new tools, run: 
`gcp_setup_billing_export_console_guide` to get step-by-step guidance

**Option 2: Manual Setup Instructions**

📋 **Step-by-Step Manual Instructions:**

1️⃣ **Open Cloud Console Billing Export**
   • Go to: https://console.cloud.google.com/billing
   • Select your billing account
   • Navigate to "Billing export" in the left menu
   • Click on the "BigQuery export" tab

2️⃣ **Configure Standard Usage Cost Export**
   • Click "Edit settings" for "Standard usage cost data"
   • Project: Select "{gcp_provider.get_current_project()}"
   • Dataset ID: Select "{dataset_id}"
   • Table name prefix: {table_prefix}
   • Click "Save"

3️⃣ **Configure Detailed Usage Cost Export (Recommended)**
   • Click "Edit settings" for "Detailed usage cost data"
   • Project: Select "{gcp_provider.get_current_project()}"
   • Dataset ID: Select "{dataset_id}"
   • Table name prefix: {table_prefix}
   • Click "Save"

4️⃣ **Configure Pricing Data Export (Optional)**
   • Click "Edit settings" for "Pricing data"
   • Project: Select "{gcp_provider.get_current_project()}"
   • Dataset ID: Select "{dataset_id}"
   • Table name prefix: {table_prefix}
   • Click "Save"

---

⏱️ **What to Expect:**
• **Standard/Detailed exports**: Data appears within a few hours
• **Retroactive data**: If using US/EU location, you'll get previous month's data
• **Pricing data**: May take up to 48 hours to appear
• **Full backfill**: May take up to 5 days for complete historical data

---

🔍 **Verification Tools:**

After setting up the exports, verify everything is working:

**Check Export Status:**
Run: `gcp_billing_export_status` to verify your exports are active

**Test Query:**
```sql
SELECT 
  service.description as service_name,
  SUM(cost) as total_cost,
  currency
FROM `{gcp_provider.get_current_project()}.{dataset_id}.{table_prefix}_*`
WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY service_name, currency
ORDER BY total_cost DESC
LIMIT 10
```

**Use Our Analysis Tools:**
Once data is flowing, run cost analysis tools like:
• `gcp_cost_analysis_summary`
• `gcp_project_cost_analysis`

---

🆘 **Need Help?**

**Common Issues:**
• **"Invalid dataset region" error**: Make sure you selected the correct project and dataset
• **No permissions**: Ensure you have Billing Account Administrator role
• **Dataset not visible**: Check that BigQuery API is enabled in the target project

**Get Detailed Troubleshooting:**
Run: `gcp_billing_setup_and_cost_guide` for comprehensive troubleshooting guide

---

💡 **Pro Tips:**
• Set up budget alerts in addition to billing export
• Consider enabling cost allocation for GKE if you use Kubernetes
• Use labels consistently across resources for better cost attribution
• Review the exported data weekly to identify optimization opportunities

🎉 **Dataset creation complete!** Now complete the Cloud Console steps above to start receiving billing data.

**Next recommended action:** Follow the manual setup instructions above, or restart the MCP server and run `gcp_setup_billing_export_console_guide` for guided setup assistance.
"""

            return project_setup_result + billing_export_setup

        except Exception as e:
            logger.error(f"Error in interactive billing export setup: {str(e)}")
            return f"""
❌ **Setup Error**: {str(e)}

🔄 **Alternative Approaches:**

1. **Manual Setup**: Run `gcp_billing_setup_and_cost_guide` for complete manual instructions
2. **Check Permissions**: Ensure you have BigQuery Admin and Billing Account Administrator roles
3. **Verify APIs**: Make sure BigQuery and BigQuery Data Transfer Service APIs are enabled

**Direct Console Link:**
https://console.cloud.google.com/billing → Billing export → BigQuery export
"""

    @mcp.tool()
    async def gcp_setup_billing_export_execute(
        dataset_id: str = "billing_export",
        location: str = "US",
        table_prefix: str = "gcp_billing_export",
        create_project: bool = False,
        project_name: str = "finops-billing-analysis",
        confirmed: bool = False
    ) -> str:
        """
        🚀 Execute BigQuery Billing Export Setup (After Confirmation).
        
        This tool actually creates the BigQuery dataset and provides setup instructions.
        Use this ONLY after reviewing the configuration with gcp_setup_billing_export_interactive.
        
        🚨 CRITICAL FOR LLMs:
        - This tool CREATES ACTUAL RESOURCES
        - NEVER call this without explicit user confirmation
        - User must explicitly say "yes, create it" or similar
        - DO NOT call this automatically after showing configuration
        - ALWAYS pause and wait for user approval first
        - ALWAYS show the complete response from this tool to the user
        
        Args:
            dataset_id: Name for the BigQuery dataset
            location: BigQuery dataset location
            table_prefix: Prefix for billing tables
            create_project: Whether to create a new dedicated FinOps project
            project_name: Name for new project if create_project=True
            confirmed: Must be set to true to proceed with creation (ONLY after user confirms)
        """
        logger.info(f"🚀 Executing BigQuery dataset creation for billing export: {dataset_id}")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        # Safety check - require explicit confirmation
        if not confirmed:
            return """
⚠️ **Confirmation Required**

This tool will create BigQuery resources. You must explicitly confirm by setting confirmed=true.

**First, review your configuration:**
Run: `gcp_setup_billing_export_interactive` to see all options and settings.

**Then, execute with confirmation:**
```
gcp_setup_billing_export_execute(
    dataset_id="your_dataset_name",
    location="your_location",
    table_prefix="your_prefix",
    confirmed=true
)
```

💡 **Safety Feature**: This prevents accidental resource creation.
"""

        try:
            # Validate location
            valid_locations = [
                "US", "EU", 
                "northamerica-northeast1", "southamerica-east1", "us-central1", 
                "us-east1", "us-east4", "us-west1", "us-west2", "us-west3", "us-west4",
                "asia-east1", "asia-east2", "asia-northeast1", "asia-northeast2", 
                "asia-northeast3", "asia-south1", "asia-southeast1", "asia-southeast2", 
                "australia-southeast1", "europe-central2", "europe-north1", 
                "europe-west1", "europe-west2", "europe-west3", "europe-west4", "europe-west6"
            ]
            
            if location not in valid_locations:
                return f"""
❌ **Invalid location**: {location}

📍 **Valid BigQuery locations for billing data:**

**Multi-region (Recommended):**
• US - Best performance, includes retroactive data
• EU - GDPR compliance, includes retroactive data

**Supported Regions:**
• Americas: {', '.join([loc for loc in valid_locations if loc.startswith(('northamerica', 'southamerica', 'us-'))])}
• Asia Pacific: {', '.join([loc for loc in valid_locations if loc.startswith(('asia-', 'australia-'))])}  
• Europe: {', '.join([loc for loc in valid_locations if loc.startswith('europe-')])}

💡 **Recommendation**: Use 'US' or 'EU' for best results and retroactive data inclusion.
"""

            # Step 1: Project setup (if requested)
            project_setup_result = ""
            if create_project:
                project_setup_result = f"""
🏗️ **Project Creation Status:**
⚠️ Note: Automatic project creation requires additional permissions and setup.
For now, please create the project manually:

1. Go to Google Cloud Console → Project Selector → New Project
2. Project Name: {project_name}
3. Ensure it's linked to your billing account
4. Enable BigQuery API and BigQuery Data Transfer Service API

Once created, switch to that project and re-run this tool.

---
"""

            # Step 2: Create BigQuery dataset
            logger.info(f"Creating BigQuery dataset '{dataset_id}' in location '{location}'")
            
            success, message = gcp_provider.setup_billing_export_with_preferences(
                dataset_id=dataset_id,
                location=location,
                table_prefix=table_prefix
            )

            if not success:
                return f"""
❌ **Dataset Creation Failed**: {message}

🔧 **Troubleshooting Steps:**
1. Ensure BigQuery API is enabled in your project
2. Verify you have BigQuery Admin permissions
3. Check that the dataset name '{dataset_id}' is valid and unique
4. Confirm the location '{location}' is supported

**Manual Alternative:**
You can create the dataset manually in BigQuery console and then run the manual setup guide.
"""

            # Step 3: Provide comprehensive manual setup instructions
            manual_instructions = f"""
✅ **Dataset Created Successfully!**
{message}

---

🎯 **Next Steps: Enable Billing Export in Cloud Console**

**IMPORTANT**: The actual billing export must be configured through the Google Cloud Console.
We've prepared your BigQuery dataset, now you need to connect it to your billing data.

**📋 Step-by-Step Instructions:**

1️⃣ **Open Cloud Console Billing Export**
   • Go to: https://console.cloud.google.com/billing
   • Select your billing account
   • Navigate to "Billing export" in the left menu
   • Click on the "BigQuery export" tab

2️⃣ **Configure Standard Usage Cost Export**
   • Click "Edit settings" for "Standard usage cost data"
   • Project: Select "{gcp_provider.get_current_project()}"
   • Dataset ID: Select "{dataset_id}"
   • Click "Save"

3️⃣ **Configure Detailed Usage Cost Export (Recommended)**
   • Click "Edit settings" for "Detailed usage cost data"
   • Project: Select "{gcp_provider.get_current_project()}"
   • Dataset ID: Select "{dataset_id}"
   • Click "Save"

4️⃣ **Configure Pricing Data Export (Optional)**
   • Click "Edit settings" for "Pricing data"
   • Project: Select "{gcp_provider.get_current_project()}"
   • Dataset ID: Select "{dataset_id}"
   • Click "Save"

---

⏱️ **What to Expect:**
• **Standard/Detailed exports**: Data appears within a few hours
• **Retroactive data**: If using US/EU location, you'll get previous month's data
• **Pricing data**: May take up to 48 hours to appear
• **Full backfill**: May take up to 5 days for complete historical data

---

🔍 **Verification Steps:**

After setting up the exports, verify everything is working:

1. **Check Dataset Tables** (after a few hours):
   • Go to BigQuery → {gcp_provider.get_current_project()} → {dataset_id}
   • Look for tables like: gcp_billing_export_*, cloud_pricing_export

2. **Run Test Query**:
   ```sql
   SELECT 
     service.description as service_name,
     SUM(cost) as total_cost,
     currency
   FROM `{gcp_provider.get_current_project()}.{dataset_id}.gcp_billing_export_*`
   WHERE _PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
   GROUP BY service_name, currency
   ORDER BY total_cost DESC
   LIMIT 10
   ```

3. **Use Our Analysis Tools**:
   Once data is flowing, you can use our comprehensive cost analysis tools!

---

🆘 **Need Help?**

**Common Issues:**
• **"Invalid dataset region" error**: Make sure you selected the correct project and dataset
• **No permissions**: Ensure you have Billing Account Administrator role
• **Dataset not visible**: Check that BigQuery API is enabled in the target project

**Get Detailed Troubleshooting:**
Run: `gcp_billing_setup_and_cost_guide` for comprehensive troubleshooting guide

**Check Current Status:**
Run: `gcp_billing_account_info` to verify your billing account access

---

💡 **Pro Tips:**
• Set up budget alerts in addition to billing export
• Consider enabling cost allocation for GKE if you use Kubernetes
• Use labels consistently across resources for better cost attribution
• Review the exported data weekly to identify optimization opportunities

🎉 **You're almost done!** Complete the Cloud Console steps above and you'll have comprehensive billing data for analysis.
"""

            return project_setup_result + manual_instructions

        except Exception as e:
            logger.error(f"Error in billing export execution: {str(e)}")
            return f"""
❌ **Execution Error**: {str(e)}

🔄 **Alternative Approaches:**

1. **Manual Setup**: Run `gcp_billing_setup_and_cost_guide` for complete manual instructions
2. **Check Permissions**: Ensure you have BigQuery Admin and Billing Account Administrator roles
3. **Verify APIs**: Make sure BigQuery and BigQuery Data Transfer Service APIs are enabled

**Direct Console Link:**
https://console.cloud.google.com/billing → Billing export → BigQuery export
"""

    @mcp.tool()
    async def gcp_project_info(project_id: Optional[str] = None) -> str:
        """Get detailed information about a GCP project."""
        logger.info(f"🔍 Getting info for GCP project: {project_id or 'current'}")
        
        try:
            info = gcp_provider.get_project_info(project_id)
            
            if not info:
                return f"❌ Failed to get project information for: {project_id or 'current project'}"
            
            # Generate report
            report = f"""
            GCP Project Information:
            
            📋 Project Details:
            - Project ID: {info['project_id']}
            - Name: {info['name']}
            - Number: {info['number']}
            - State: {info['state']}
            - Created: {info['create_time']}
            """
            
            if info.get('labels'):
                report += "\n🏷️ Labels:\n"
                for key, value in info['labels'].items():
                    report += f"- {key}: {value}\n"
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to get GCP project info: {str(e)}", "gcp")
            return f"Error getting GCP project info: {str(e)}"

    @mcp.tool()
    async def gcp_setup_billing_export_console_guide(
        random_string: str = ""
    ) -> str:
        """
        🎯 Interactive Console Guide for GCP Billing Export Setup.
        
        Provides step-by-step guidance for setting up billing export in the Google Cloud Console
        after the BigQuery dataset has been created.
        
        🚨 FOR LLMs: ALWAYS show the complete response from this tool to the user.
        This contains step-by-step instructions the user needs to follow.
        """
        logger.info("🎯 Starting interactive console guide for billing export setup...")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        try:
            current_project = gcp_provider.get_current_project()
            billing_account_info = gcp_provider.get_billing_account_info()
            
            # Check for existing billing export datasets
            existing_datasets = gcp_provider._check_existing_billing_export()
            
            guide = f"""
🎯 **Interactive GCP Billing Export Setup Guide**

📊 **Current Status:**
• **Project**: {current_project}
• **Billing Account**: {billing_account_info.get('display_name', 'Unknown')} ({billing_account_info.get('name', 'Unknown')})
• **Existing Datasets**: {', '.join(existing_datasets) if existing_datasets else 'None found'}

---

🚀 **Step-by-Step Console Setup**

**🔗 Quick Links:**
• **Billing Console**: https://console.cloud.google.com/billing
• **BigQuery Console**: https://console.cloud.google.com/bigquery
• **Project Console**: https://console.cloud.google.com/home/dashboard?project={current_project}

---

**1️⃣ OPEN BILLING EXPORT SETTINGS**

📋 **Instructions:**
1. Open: https://console.cloud.google.com/billing
2. Select billing account: "{billing_account_info.get('display_name', 'Your billing account')}"
3. In left sidebar, click "Billing export"
4. Click on "BigQuery export" tab

✅ **Verification**: You should see three export options:
   • Standard usage cost data
   • Detailed usage cost data  
   • Pricing data

---

**2️⃣ CONFIGURE STANDARD USAGE EXPORT (Required)**

📋 **Instructions:**
1. Find "Standard usage cost data" section
2. Click "Edit settings" button
3. **Project**: Select "{current_project}"
4. **Dataset ID**: Select or type "billing_export" (or your chosen dataset)
5. **Table name prefix**: Enter "gcp_billing_export"
6. Click "Save"

✅ **Verification**: Status should change to "Enabled" with green checkmark

---

**3️⃣ CONFIGURE DETAILED USAGE EXPORT (Recommended)**

📋 **Instructions:**
1. Find "Detailed usage cost data" section
2. Click "Edit settings" button
3. **Project**: Select "{current_project}"
4. **Dataset ID**: Select or type "billing_export" (same as above)
5. **Table name prefix**: Enter "gcp_billing_export" (same as above)
6. Click "Save"

✅ **Verification**: Status should change to "Enabled" with green checkmark

💡 **Why enable detailed export?**
   • Resource-level cost breakdown
   • VM instance details, disk usage, etc.
   • Better cost optimization insights

---

**4️⃣ CONFIGURE PRICING DATA EXPORT (Optional)**

📋 **Instructions:**
1. Find "Pricing data" section
2. Click "Edit settings" button
3. **Project**: Select "{current_project}"
4. **Dataset ID**: Select or type "billing_export" (same as above)
5. **Table name prefix**: Enter "gcp_billing_export" (same as above)
6. Click "Save"

✅ **Verification**: Status should change to "Enabled" with green checkmark

💡 **Why enable pricing export?**
   • SKU-level pricing information
   • Track price changes over time
   • Advanced cost modeling

---

**5️⃣ VERIFY SETUP**

📋 **Check Export Status:**
After saving, you should see:
• ✅ Standard usage cost data: **Enabled**
• ✅ Detailed usage cost data: **Enabled**  
• ✅ Pricing data: **Enabled** (if configured)

📋 **Check BigQuery Dataset:**
1. Go to: https://console.cloud.google.com/bigquery
2. In Explorer panel, find your project "{current_project}"
3. Look for "billing_export" dataset
4. You should see it listed (tables will appear as data flows in)

---

**⏱️ TIMELINE EXPECTATIONS**

**First 24 Hours:**
• Dataset appears in BigQuery immediately
• Standard/Detailed export tables start appearing within 4-6 hours
• Pricing data may take up to 24 hours

**First Week:**
• If using US/EU location: Previous month's data backfills (up to 5 days)
• Current usage data flows daily
• Tables are partitioned by date (one per day)

**Ongoing:**
• Data updates multiple times per day
• Previous day's data is usually complete by noon UTC
• Costs may be updated retroactively for up to 30 days

---

**🔍 VERIFICATION TOOLS**

**Run These Commands After Setup:**

**Check Export Status:**
```
gcp_billing_export_status
```

**Test Data Availability:**
```
gcp_billing_export_test_query
```

**Start Cost Analysis:**
```
gcp_cost_analysis_summary
```

---

**🚨 TROUBLESHOOTING**

**Common Issues:**

**❌ "Dataset not found" error:**
• Make sure BigQuery API is enabled
• Verify dataset was created in correct project
• Check dataset location matches billing export requirements

**❌ "Insufficient permissions" error:**
• Need "Billing Account Administrator" role
• Need "BigQuery Admin" role on target project
• Contact your GCP admin if you don't have these roles

**❌ "Invalid dataset region" error:**
• Dataset location must be US, EU, or supported region
• Recreate dataset in supported location if needed

**❌ No data appearing after 24 hours:**
• Verify export settings are "Enabled"
• Check if billing account has recent activity
• Confirm dataset permissions allow billing service access

---

**📞 GET HELP**

**Need Assistance?**
• Run `gcp_billing_setup_and_cost_guide` for detailed troubleshooting
• Check Google Cloud documentation: https://cloud.google.com/billing/docs/how-to/export-data-bigquery
• Contact your GCP administrator for permission issues

**Ready to Verify?**
Once you've completed the console setup, run:
```
gcp_billing_export_status
```

🎉 **You're doing great!** Complete the console steps above and you'll have comprehensive billing data flowing into BigQuery.
"""

            return guide

        except Exception as e:
            logger.error(f"Error in console guide: {str(e)}")
            return f"""
❌ **Error generating console guide**: {str(e)}

🔄 **Alternative Resources:**
• **Direct Console Link**: https://console.cloud.google.com/billing
• **Documentation**: https://cloud.google.com/billing/docs/how-to/export-data-bigquery
• **Manual Setup Guide**: Run `gcp_billing_setup_and_cost_guide`
"""

    @mcp.tool()
    async def gcp_bigquery_datasets_list(
        random_string: str = ""
    ) -> str:
        """
        📊 List all BigQuery datasets in the current project.
        
        Shows all datasets with details about tables and potential billing data.
        
        🚨 FOR LLMs: ALWAYS show the complete response from this tool to the user.
        This contains important information about existing BigQuery resources.
        """
        logger.info("📊 Listing BigQuery datasets...")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        try:
            current_project = gcp_provider.get_current_project()
            if not current_project:
                return "❌ No current GCP project set. Please configure your GCP project first."

            datasets = gcp_provider.list_bigquery_datasets()
            
            if not datasets:
                return f"""
📊 **BigQuery Datasets in Project: {current_project}**

❌ **No BigQuery datasets found**

This could mean:
• BigQuery API is not enabled
• No datasets have been created yet
• Insufficient permissions to list datasets

**Next Steps:**
1. Enable BigQuery API: `gcloud services enable bigquery.googleapis.com`
2. Check permissions: You need BigQuery Data Viewer role
3. Create your first dataset for billing export

**To create billing export dataset:**
Run: `gcp_setup_billing_export_interactive`
"""

            # Analyze datasets for billing data
            billing_datasets = [d for d in datasets if d['has_billing_data']]
            regular_datasets = [d for d in datasets if not d['has_billing_data']]
            
            report = f"""
📊 **BigQuery Datasets in Project: {current_project}**

**Total Datasets Found: {len(datasets)}**
• **With Billing Data**: {len(billing_datasets)}
• **Regular Datasets**: {len(regular_datasets)}

---

"""

            if billing_datasets:
                report += "🎯 **DATASETS WITH BILLING DATA:**\n\n"
                for dataset in billing_datasets:
                    report += f"✅ **{dataset['dataset_id']}**\n"
                    report += f"   • Location: {dataset['location']}\n"
                    report += f"   • Tables: {dataset['table_count']} total\n"
                    report += f"   • Billing Tables: {len(dataset['billing_tables'])}\n"
                    if dataset['billing_tables']:
                        report += f"   • Billing Table Names: {', '.join(dataset['billing_tables'][:3])}\n"
                        if len(dataset['billing_tables']) > 3:
                            report += f"     ... and {len(dataset['billing_tables']) - 3} more\n"
                    report += f"   • Created: {dataset['created']}\n"
                    if dataset['description']:
                        report += f"   • Description: {dataset['description']}\n"
                    report += "\n"

            if regular_datasets:
                report += "📁 **OTHER DATASETS:**\n\n"
                for dataset in regular_datasets:
                    report += f"📋 **{dataset['dataset_id']}**\n"
                    report += f"   • Location: {dataset['location']}\n"
                    report += f"   • Tables: {dataset['table_count']}\n"
                    report += f"   • Created: {dataset['created']}\n"
                    if dataset['description']:
                        report += f"   • Description: {dataset['description']}\n"
                    report += "\n"

            if billing_datasets:
                report += """
---

🎉 **GREAT NEWS: You have billing data!**

**Next Steps:**
1. **Verify Data Flow**: Run `gcp_billing_export_test_query` to check recent data
2. **Analyze Costs**: Use `gcp_cost_analysis_summary` for insights
3. **Check Export Status**: Verify exports are active in GCP Console

**Available Analysis Tools:**
• `gcp_project_cost_analysis` - Project-level cost breakdown
• `gcp_compute_cost_analysis` - Compute Engine analysis
• `gcp_gke_cost_deep_dive` - Kubernetes cost analysis
"""
            else:
                report += """
---

💡 **No Billing Data Found**

None of your datasets contain billing export tables. To get cost insights:

**Option 1: Set up billing export**
Run: `gcp_setup_billing_export_interactive`

**Option 2: Check if you have billing export in another project**
Run: `gcp_project_list` to see other projects

**Option 3: Manual setup**
Go to: https://console.cloud.google.com/billing → Billing export
"""

            return report

        except Exception as e:
            logger.error(f"Error listing BigQuery datasets: {str(e)}")
            return f"""
❌ **Error listing BigQuery datasets**: {str(e)}

🔧 **Troubleshooting:**
1. Ensure BigQuery API is enabled: `gcloud services enable bigquery.googleapis.com`
2. Verify you have BigQuery Data Viewer permissions
3. Check that your GCP credentials are valid

**Manual Check:**
Go to BigQuery console: https://console.cloud.google.com/bigquery
"""

    @mcp.tool()
    async def gcp_billing_export_status(
        random_string: str = ""
    ) -> str:
        """
        🔍 Check the status of GCP billing export setup and data availability.
        
        Verifies if billing export is configured and working properly.
        
        🚨 FOR LLMs: ALWAYS show the complete response from this tool to the user.
        This contains important status information about their billing export setup.
        """
        logger.info("🔍 Checking GCP billing export status...")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        try:
            current_project = gcp_provider.get_current_project()
            if not current_project:
                return "❌ No current GCP project set. Please configure your GCP project first."

            # Get all BigQuery datasets
            datasets = gcp_provider.list_bigquery_datasets()
            
            # Filter for billing datasets
            billing_datasets = [d for d in datasets if d['has_billing_data']]
            
            if not billing_datasets:
                return f"""
❌ **No Billing Export Datasets Found**

📊 **Current Project**: {current_project}
📋 **Total BigQuery Datasets**: {len(datasets)}
🔍 **Datasets with Billing Data**: 0

**Analysis:**
• Found {len(datasets)} BigQuery dataset(s) in your project
• None contain billing export tables
• You need to set up billing export to get cost insights

**Next Steps:**
1. **Create Billing Export**: Run `gcp_setup_billing_export_interactive`
2. **List All Datasets**: Run `gcp_bigquery_datasets_list` to see what you have
3. **Manual Setup**: Run `gcp_billing_setup_and_cost_guide`
4. **Check Different Project**: Switch to project containing billing data

**Quick Setup:**
```
gcp_setup_billing_export_interactive(confirmed=true)
```
"""

            # Analyze billing datasets in detail
            status_results = []
            
            for dataset_info in billing_datasets:
                dataset_id = dataset_info['dataset_id']
                billing_tables = dataset_info['billing_tables']
                
                try:
                    from google.cloud import bigquery
                    client = bigquery.Client(project=current_project)
                    dataset_ref = client.dataset(dataset_id)
                    
                    if billing_tables:
                        # Get table info for the most recent table
                        latest_table = sorted(billing_tables)[-1]
                        table_ref = dataset_ref.table(latest_table)
                        table = client.get_table(table_ref)
                        
                        # Check for recent data
                        query = f"""
                        SELECT 
                            COUNT(*) as row_count,
                            MIN(usage_start_time) as earliest_data,
                            MAX(usage_start_time) as latest_data,
                            SUM(cost) as total_cost
                        FROM `{current_project}.{dataset_id}.{latest_table}`
                        WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
                        """
                        
                        try:
                            query_job = client.query(query)
                            results = list(query_job.result())
                            
                            if results:
                                row = results[0]
                                status_results.append({
                                    'dataset': dataset_id,
                                    'dataset_info': dataset_info,
                                    'tables': len(billing_tables),
                                    'latest_table': latest_table,
                                    'row_count': row.row_count,
                                    'earliest_data': row.earliest_data,
                                    'latest_data': row.latest_data,
                                    'total_cost': row.total_cost,
                                    'status': 'active' if row.row_count > 0 else 'empty'
                                })
                            else:
                                status_results.append({
                                    'dataset': dataset_id,
                                    'dataset_info': dataset_info,
                                    'tables': len(billing_tables),
                                    'latest_table': latest_table,
                                    'status': 'no_data'
                                })
                        except Exception as query_error:
                            status_results.append({
                                'dataset': dataset_id,
                                'dataset_info': dataset_info,
                                'tables': len(billing_tables),
                                'latest_table': latest_table,
                                'status': 'query_error',
                                'error': str(query_error)
                            })
                    else:
                        status_results.append({
                            'dataset': dataset_id,
                            'dataset_info': dataset_info,
                            'tables': 0,
                            'status': 'no_billing_tables'
                        })
                        
                except Exception as dataset_error:
                    status_results.append({
                        'dataset': dataset_id,
                        'dataset_info': dataset_info,
                        'status': 'access_error',
                        'error': str(dataset_error)
                    })

            # Generate status report
            report = f"""
🔍 **GCP Billing Export Status Report**

📊 **Project**: {current_project}
📅 **Check Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
📋 **Total BigQuery Datasets**: {len(datasets)}
🎯 **Datasets with Billing Data**: {len(billing_datasets)}

---

**📋 BILLING DATASET STATUS:**

"""

            for result in status_results:
                dataset_id = result['dataset']
                status = result['status']
                
                if status == 'active':
                    dataset_info = result['dataset_info']
                    report += f"""
✅ **{dataset_id}**: ACTIVE & RECEIVING DATA
   • **Location**: {dataset_info['location']}
   • **Created**: {dataset_info['created']}
   • **Total Tables**: {dataset_info['table_count']}
   • **Billing Tables**: {result['tables']} found
   • **Latest Table**: {result['latest_table']}
   • **Recent Data**: {result['row_count']:,} rows in last 7 days
   • **Date Range**: {result['earliest_data']} to {result['latest_data']}
   • **Total Cost (7 days)**: ${result['total_cost']:.2f}
"""
                elif status == 'empty':
                    report += f"""
⚠️ **{dataset_id}**: CONFIGURED BUT NO RECENT DATA
   • Tables: {result['tables']} billing tables found
   • Latest Table: {result['latest_table']}
   • Status: No data in last 7 days (may be normal for new setups)
"""
                elif status == 'no_billing_tables':
                    report += f"""
❌ **{dataset_id}**: NO BILLING TABLES
   • Tables: {result['tables']} billing tables found
   • Status: Dataset exists but no billing export tables
   • Action: Configure billing export in Cloud Console
"""
                elif status == 'query_error':
                    report += f"""
⚠️ **{dataset_id}**: QUERY ERROR
   • Tables: {result['tables']} billing tables found
   • Latest Table: {result['latest_table']}
   • Error: {result.get('error', 'Unknown query error')}
"""
                elif status == 'access_error':
                    report += f"""
❌ **{dataset_id}**: ACCESS ERROR
   • Error: {result.get('error', 'Unknown access error')}
   • Action: Check BigQuery permissions
"""

            # Add recommendations
            active_datasets = [r for r in status_results if r['status'] == 'active']
            configured_datasets = [r for r in status_results if r['status'] in ['active', 'empty']]
            
            if active_datasets:
                report += f"""

---

🎉 **GOOD NEWS**: You have {len(active_datasets)} active billing export(s)!

**✅ Ready for Analysis:**
• Run `gcp_cost_analysis_summary` for cost insights
• Run `gcp_project_cost_analysis` for detailed breakdown
• Use BigQuery to create custom queries and dashboards

**📊 Sample Query to Get Started:**
```sql
SELECT 
  service.description as service,
  SUM(cost) as total_cost,
  currency
FROM `{current_project}.{active_datasets[0]['dataset']}.{active_datasets[0]['latest_table']}`
WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY service, currency
ORDER BY total_cost DESC
LIMIT 10
```
"""
            elif configured_datasets:
                report += f"""

---

⏳ **SETUP IN PROGRESS**: You have {len(configured_datasets)} configured dataset(s)

**Next Steps:**
1. **Wait for Data**: New exports can take 4-24 hours for first data
2. **Check Console**: Verify export settings at https://console.cloud.google.com/billing
3. **Verify Permissions**: Ensure billing service can write to BigQuery

**Check Again Later:**
```
gcp_billing_export_status
```
"""
            else:
                report += f"""

---

❌ **NO ACTIVE BILLING EXPORTS FOUND**

**Immediate Actions:**
1. **Quick Setup**: Run `gcp_setup_billing_export_interactive(confirmed=true)`
2. **Console Setup**: Run `gcp_setup_billing_export_console_guide`
3. **Manual Guide**: Run `gcp_billing_setup_and_cost_guide`

**Common Issues:**
• Billing export not configured in Cloud Console
• Dataset in wrong project or location
• Insufficient permissions (need Billing Admin + BigQuery Admin)
"""

            return report

        except Exception as e:
            logger.error(f"Error checking billing export status: {str(e)}")
            return f"""
❌ **Error checking billing export status**: {str(e)}

🔄 **Alternative Checks:**
• **Manual Console Check**: https://console.cloud.google.com/billing → Billing export
• **BigQuery Console**: https://console.cloud.google.com/bigquery
• **Setup Guide**: Run `gcp_billing_setup_and_cost_guide`

**Common Solutions:**
• Ensure BigQuery API is enabled
• Verify you have proper permissions
• Check if you're in the correct project
"""

    @mcp.tool()
    async def gcp_billing_export_test_query(
        dataset_id: str = "billing_export",
        days: int = 7
    ) -> str:
        """
        🧪 Test query to verify billing export data is flowing correctly.
        
        🚨 FOR LLMs: ALWAYS show the complete response from this tool to the user.
        This contains important verification results and sample data.
        
        Args:
            dataset_id: BigQuery dataset containing billing data
            days: Number of days to query (default: 7)
        """
        logger.info(f"🧪 Testing billing export data query for {days} days...")
        
        gcp_provider = provider_manager.get_provider("gcp")
        if not gcp_provider:
            return "❌ GCP provider not available. Please check your GCP configuration."

        try:
            current_project = gcp_provider.get_current_project()
            
            # Test query to check data availability
            from google.cloud import bigquery
            client = bigquery.Client(project=current_project)
            
            # First, check if dataset exists
            try:
                dataset_ref = client.dataset(dataset_id)
                dataset = client.get_dataset(dataset_ref)
            except Exception:
                return f"""
❌ **Dataset Not Found**: {dataset_id}

**Available Datasets:**
Run `gcp_billing_export_status` to see available billing datasets.

**Create Dataset:**
```
gcp_setup_billing_export_interactive(confirmed=true)
```
"""

            # Find billing tables
            tables = list(client.list_tables(dataset_ref))
            billing_tables = [t.table_id for t in tables if 'billing' in t.table_id.lower()]
            
            if not billing_tables:
                return f"""
❌ **No Billing Tables Found** in dataset {dataset_id}

**Found Tables:** {[t.table_id for t in tables][:5]}

**Next Steps:**
1. Configure billing export in Cloud Console
2. Run `gcp_setup_billing_export_console_guide` for guidance
3. Wait 4-24 hours for data to appear
"""

            # Use the most recent billing table
            table_pattern = f"`{current_project}.{dataset_id}.gcp_billing_export_*`"
            
            test_query = f"""
            SELECT 
                service.description as service_name,
                sku.description as sku_description,
                project.id as project_id,
                location.location as location,
                usage_start_time,
                usage_end_time,
                cost,
                currency,
                credits,
                usage.amount as usage_amount,
                usage.unit as usage_unit
            FROM {table_pattern}
            WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            ORDER BY usage_start_time DESC, cost DESC
            LIMIT 10
            """
            
            logger.info(f"Executing test query: {test_query}")
            query_job = client.query(test_query)
            results = list(query_job.result())
            
            if not results:
                return f"""
⚠️ **No Recent Data Found** (last {days} days)

**Possible Reasons:**
• Billing export recently configured (data takes 4-24 hours)
• No billable activity in the last {days} days
• Export configured but not working

**Troubleshooting:**
1. Check export status: `gcp_billing_export_status`
2. Try longer period: `gcp_billing_export_test_query(days=30)`
3. Verify console setup: `gcp_setup_billing_export_console_guide`

**Available Tables:** {', '.join(billing_tables[:5])}
"""

            # Format results
            report = f"""
✅ **Billing Export Test Query Results**

📊 **Query Details:**
• **Project**: {current_project}
• **Dataset**: {dataset_id}
• **Period**: Last {days} days
• **Records Found**: {len(results)}

---

**📋 SAMPLE DATA (Top 10 Recent Charges):**

"""

            for i, row in enumerate(results, 1):
                cost_display = f"${row.cost:.4f}" if row.cost else "$0.0000"
                credits_display = f"${abs(row.credits):.4f} credit" if row.credits else "No credits"
                
                report += f"""
**{i}. {row.service_name}**
   • SKU: {row.sku_description[:60]}{'...' if len(row.sku_description) > 60 else ''}
   • Project: {row.project_id}
   • Location: {row.location or 'Global'}
   • Time: {row.usage_start_time.strftime('%Y-%m-%d %H:%M')} - {row.usage_end_time.strftime('%Y-%m-%d %H:%M')}
   • Cost: {cost_display} {row.currency}
   • Credits: {credits_display}
   • Usage: {row.usage_amount} {row.usage_unit}

"""

            # Add summary statistics
            total_cost = sum(row.cost for row in results if row.cost)
            total_credits = sum(abs(row.credits) for row in results if row.credits)
            unique_services = len(set(row.service_name for row in results))
            unique_projects = len(set(row.project_id for row in results))
            
            report += f"""
---

**📊 SUMMARY STATISTICS (Sample Data):**
• **Total Cost**: ${total_cost:.2f}
• **Total Credits**: ${total_credits:.2f}
• **Unique Services**: {unique_services}
• **Unique Projects**: {unique_projects}
• **Date Range**: {results[-1].usage_start_time.strftime('%Y-%m-%d')} to {results[0].usage_start_time.strftime('%Y-%m-%d')}

---

**🎉 SUCCESS**: Your billing export is working correctly!

**Next Steps:**
• **Full Analysis**: Run `gcp_cost_analysis_summary`
• **Project Breakdown**: Run `gcp_project_cost_analysis`
• **Custom Queries**: Use BigQuery console for detailed analysis

**Sample Advanced Query:**
```sql
SELECT 
  service.description as service,
  SUM(cost) as total_cost,
  SUM(ARRAY_LENGTH(credits)) as credit_count,
  COUNT(*) as usage_records
FROM {table_pattern}
WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY service
ORDER BY total_cost DESC
```
"""

            return report

        except Exception as e:
            logger.error(f"Error in billing export test query: {str(e)}")
            return f"""
❌ **Test Query Failed**: {str(e)}

🔧 **Troubleshooting:**
• **Check Permissions**: Ensure you have BigQuery Data Viewer role
• **Verify Dataset**: Run `gcp_billing_export_status` to check setup
• **API Enabled**: Ensure BigQuery API is enabled
• **Table Format**: Billing tables use specific naming patterns

**Alternative Checks:**
• **Console Query**: Use BigQuery console to run queries manually
• **Setup Verification**: Run `gcp_setup_billing_export_console_guide`
""" 