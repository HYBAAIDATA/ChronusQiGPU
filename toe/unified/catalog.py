"""Pre-built enterprise connector catalog.

Each entry is a bindable system: vendor, product, the system class it
displaces, protocol, auth scheme, and the entities it serves. Drivers live
in ``connectors.py``. A connector with no bound credentials does not invent
rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


DISPLACED_CLASSES: tuple[str, ...] = (
    "data_warehouse",
    "bi",
    "ml_platform",
    "ai_framework",
    "etl",
    "crm",
    "erp",
    "hcm",
    "data_quality",
    "governance",
    "streaming",
    "visualization",
    "feature_store",
    "experiment_tracking",
    "reverse_etl",
    "cdp",
    "mdm",
    "observability",
    "iam",
)


@dataclass(frozen=True)
class ConnectorSpec:
    id: str
    vendor: str
    product: str
    category: str
    protocol: str
    auth: str
    entities: tuple[str, ...]
    industries: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "vendor": self.vendor,
            "product": self.product,
            "category": self.category,
            "protocol": self.protocol,
            "auth": self.auth,
            "entities": list(self.entities),
            "industries": list(self.industries),
        }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _pack(
    vendor: str,
    category: str,
    protocol: str,
    auth: str,
    entities: str,
    industries: str,
    products: tuple[str, ...],
) -> list[ConnectorSpec]:
    if category not in DISPLACED_CLASSES:
        raise ValueError(f"unknown displaced class: {category}")
    ents = tuple(part.strip() for part in entities.split(",") if part.strip())
    inds = tuple(part.strip() for part in industries.split(",") if part.strip())
    specs = []
    for product in products:
        specs.append(
            ConnectorSpec(
                id=f"{_slug(vendor)}.{_slug(product)}",
                vendor=vendor,
                product=product,
                category=category,
                protocol=protocol,
                auth=auth,
                entities=ents,
                industries=inds,
            )
        )
    return specs


def _build() -> tuple[ConnectorSpec, ...]:
    groups: list[ConnectorSpec] = []
    add = groups.extend
    add(_pack("SAP", "erp", "odata", "oauth2", "BusinessPartner,JournalEntry,SalesOrder", "cross_industry,manufacturing,financial_services", (
        "S/4HANA", "S/4HANA Cloud", "ECC", "Business One", "Business ByDesign", "Ariba Buying", "Ariba Sourcing",
        "Concur Expense", "Concur Invoice", "Concur Travel", "Fieldglass", "IBP", "EWM", "TM", "Digital Manufacturing",
        "Group Reporting", "Central Finance", "Treasury and Risk Management", "Subscription Billing", "Commerce Cloud",
        "CPQ", "Business Network", "Build Process Automation", "Sustainability Control Tower", "Product Footprint Management",
        "Industry Cloud Utilities", "Industry Cloud Retail", "Industry Cloud Banking", "Industry Cloud Insurance",
        "Industry Cloud Healthcare", "Plant Connectivity", "Asset Performance Management", "Field Service Management",
        "Commodity Management", "Profitability and Performance Management", "Green Ledger", "Responsible Design and Production",
        "Farm Management", "RISE", "GROW", "Private Link",
    )))
    add(_pack("SAP", "hcm", "odata", "oauth2", "Worker,Position,Compensation", "cross_industry", (
        "SuccessFactors Employee Central", "SuccessFactors Recruiting", "SuccessFactors Learning",
        "SuccessFactors Compensation", "SuccessFactors Onboarding", "SuccessFactors Time",
        "SuccessFactors Payroll", "SuccessFactors Performance", "Qualtrics EmployeeXM",
    )))
    add(_pack("SAP", "crm", "odata", "oauth2", "Account,Contact,Opportunity,Case", "cross_industry", (
        "Sales Cloud", "Service Cloud", "Marketing Cloud", "Customer Data Cloud", "Emarsys", "Qualtrics CustomerXM",
    )))
    add(_pack("SAP", "data_warehouse", "jdbc", "basic", "Fact,Dimension", "cross_industry", (
        "Datasphere", "BW/4HANA", "HANA Cloud", "IQ", "ASE", "Data Intelligence",
    )))
    add(_pack("SAP", "etl", "odata", "oauth2", "Pipeline,Task", "cross_industry", (
        "Integration Suite", "Cloud Integration", "Data Services", "Event Mesh", "API Management", "Data Intelligence Pipelines",
    )))
    add(_pack("SAP", "bi", "odata", "oauth2", "Story,Model", "cross_industry", (
        "Analytics Cloud", "BusinessObjects", "Crystal Reports", "Web Intelligence", "Lumira", "Analysis for Office",
    )))
    add(_pack("SAP", "mdm", "odata", "oauth2", "BusinessPartner,Product", "cross_industry", (
        "MDG", "Information Steward", "Master Data Integration",
    )))
    add(_pack("SAP", "governance", "odata", "oauth2", "Control,Risk", "cross_industry,financial_services", (
        "GRC Access Control", "GRC Process Control", "Cloud ALM", "Solution Manager", "Focused Run", "Signavio", "LeanIX",
    )))
    add(_pack("SAP", "iam", "odata", "oauth2", "User,Role", "cross_industry", (
        "Identity Authentication", "Identity Provisioning",
    )))
    add(_pack("SAP", "ai_framework", "rest", "oauth2", "Prompt,Document", "cross_industry", (
        "Joule", "Conversational AI", "Predictive Analytics",
    )))
    add(_pack("Oracle", "erp", "rest", "oauth2", "Ledger,Invoice,PurchaseOrder", "cross_industry,manufacturing", (
        "Fusion Cloud ERP", "Fusion Cloud SCM", "NetSuite", "NetSuite OneWorld", "JD Edwards EnterpriseOne",
        "PeopleSoft Financials", "Procurement Cloud", "Inventory Management", "Manufacturing Cloud",
        "Maintenance Cloud", "Order Management", "Product Hub", "Transportation Management",
        "Warehouse Management", "Global Trade Management", "Subscription Management", "Revenue Management",
        "Billing and Revenue Management",
    )))
    add(_pack("Oracle", "hcm", "rest", "oauth2", "Worker,Assignment,Payroll", "cross_industry", (
        "Fusion Cloud HCM", "PeopleSoft HCM", "PeopleSoft Campus", "Taleo",
    )))
    add(_pack("Oracle", "crm", "rest", "oauth2", "Account,Contact,Opportunity", "cross_industry", (
        "Fusion CX Sales", "Fusion CX Service", "Siebel", "Eloqua", "Responsys", "CPQ Cloud", "Commerce", "Unity CDP Sales",
    )))
    add(_pack("Oracle", "data_warehouse", "jdbc", "basic", "Fact,Dimension", "cross_industry", (
        "Autonomous Data Warehouse", "Exadata", "Database 19c", "Database 23ai", "MySQL HeatWave", "Essbase",
    )))
    add(_pack("Oracle", "etl", "rest", "oauth2", "Pipeline,Replication", "cross_industry", (
        "GoldenGate", "Data Integrator", "OCI Data Integration", "OCI Data Flow", "Integration Cloud",
    )))
    add(_pack("Oracle", "bi", "rest", "oauth2", "Workbook,Analysis", "cross_industry", (
        "Analytics Cloud", "BI Publisher", "Hyperion Planning", "Hyperion Financial Management",
    )))
    add(_pack("Oracle", "ml_platform", "rest", "oauth2", "Model,Notebook", "cross_industry", (
        "OCI Data Science", "HeatWave AutoML",
    )))
    add(_pack("Oracle", "cdp", "rest", "oauth2", "Profile,Segment", "cross_industry", ("Unity CDP", "Infinity")))
    add(_pack("Oracle", "governance", "rest", "oauth2", "Catalog,Policy", "cross_industry", ("OCI Data Catalog", "APEX")))
    add(_pack("Microsoft", "erp", "odata", "oauth2", "Company,Ledger,Item", "cross_industry,manufacturing", (
        "Dynamics 365 Finance", "Dynamics 365 Supply Chain", "Dynamics 365 Commerce", "Dynamics 365 Project Operations",
        "Dynamics 365 Business Central", "Dynamics AX", "Dynamics NAV", "Dynamics GP", "Dynamics SL",
    )))
    add(_pack("Microsoft", "crm", "odata", "oauth2", "Account,Contact,Opportunity,Case", "cross_industry", (
        "Dynamics 365 Sales", "Dynamics 365 Customer Service", "Dynamics 365 Field Service",
        "Dynamics 365 Customer Insights", "Dynamics 365 Fraud Protection",
    )))
    add(_pack("Microsoft", "hcm", "odata", "oauth2", "Worker,Leave,Compensation", "cross_industry", (
        "Dynamics 365 Human Resources", "Viva Insights", "Viva Learning",
    )))
    add(_pack("Microsoft", "data_warehouse", "jdbc", "oauth2", "Fact,Dimension", "cross_industry", (
        "Fabric Warehouse", "Synapse Analytics", "SQL Server", "Azure SQL", "Analysis Services",
    )))
    add(_pack("Microsoft", "etl", "rest", "oauth2", "Pipeline,Dataflow", "cross_industry", (
        "Azure Data Factory", "SSIS", "Logic Apps", "Power Automate",
    )))
    add(_pack("Microsoft", "bi", "rest", "oauth2", "Report,Dataset", "cross_industry", (
        "Power BI", "SSRS", "SSAS", "Power Pages",
    )))
    add(_pack("Microsoft", "ml_platform", "rest", "oauth2", "Model,Endpoint", "cross_industry", (
        "Azure Machine Learning", "Azure Databricks",
    )))
    add(_pack("Microsoft", "ai_framework", "rest", "oauth2", "Deployment,Prompt", "cross_industry", (
        "Azure OpenAI", "Cognitive Services",
    )))
    add(_pack("Microsoft", "streaming", "kafka", "oauth2", "Event", "cross_industry", (
        "Event Hubs", "Stream Analytics", "Service Bus",
    )))
    add(_pack("Microsoft", "governance", "rest", "oauth2", "Asset,Classification", "cross_industry", (
        "Purview", "Master Data Services", "Dataverse",
    )))
    add(_pack("Microsoft", "iam", "rest", "oauth2", "User,Group,Role", "cross_industry", ("Entra ID", "Intune")))
    add(_pack("Microsoft", "observability", "rest", "oauth2", "Metric,Log,Trace", "cross_industry", (
        "Azure Monitor", "Log Analytics", "Application Insights", "Sentinel", "Defender for Cloud",
    )))
    add(_pack("Microsoft", "mdm", "odata", "oauth2", "Customer,Product", "cross_industry", ("Common Data Model",)))
    add(_pack("Salesforce", "crm", "rest", "oauth2", "Account,Contact,Lead,Opportunity,Case", "cross_industry,financial_services", (
        "Sales Cloud", "Service Cloud", "Marketing Cloud", "Commerce Cloud", "Experience Cloud", "Data Cloud",
        "Revenue Cloud", "CPQ", "Field Service", "Industries Health", "Industries Financial Services",
        "Industries Manufacturing", "Pardot", "Tableau CRM", "MuleSoft Anypoint", "Slack", "Heroku Connect",
        "Platform Events", "Change Data Capture", "Bulk API",
    )))
    add(_pack("Salesforce", "cdp", "rest", "oauth2", "Profile,Segment,Activation", "cross_industry", (
        "Data Cloud Profiles", "Data Cloud Segments", "Data Cloud Activations",
    )))
    add(_pack("Workday", "hcm", "rest", "oauth2", "Worker,Position,Compensation,Absence", "cross_industry", (
        "Human Capital Management", "Recruiting", "Learning", "Payroll", "Time Tracking", "Talent",
        "People Analytics", "Adaptive Planning", "Prism", "Financial Management", "Procurement",
        "Projects", "Grants", "Student", "Extend",
    )))
    add(_pack("Workday", "erp", "rest", "oauth2", "Ledger,SupplierInvoice,Journal", "cross_industry", (
        "Core Financials", "Expenses", "Inventory", "Revenue Management",
    )))
    add(_pack("ServiceNow", "erp", "rest", "oauth2", "Task,Incident,Change", "cross_industry", (
        "IT Service Management", "IT Operations Management", "HR Service Delivery", "Customer Service Management",
        "Security Operations", "Governance Risk Compliance", "Strategic Portfolio Management",
        "Field Service Management", "Integration Hub", "Flow Designer", "CMDB", "Discovery",
        "App Engine", "Now Assist",
    )))
    add(_pack("ServiceNow", "observability", "rest", "oauth2", "Event,Metric", "cross_industry", (
        "Event Management", "Health Log Analytics",
    )))
    add(_pack("ServiceNow", "mdm", "rest", "oauth2", "CI,Service", "cross_industry", ("CMDB Classes",)))
    add(_pack("Adobe", "crm", "rest", "oauth2", "Profile,Campaign,Journey", "cross_industry", (
        "Experience Platform", "Real-Time CDP", "Journey Optimizer", "Campaign", "Marketo",
        "Analytics", "Target", "Audience Manager", "Commerce", "Workfront",
    )))
    add(_pack("Google", "data_warehouse", "jdbc", "oauth2", "Table,View", "cross_industry", (
        "BigQuery", "BigQuery Omni", "AlloyDB", "Cloud SQL", "Spanner",
    )))
    add(_pack("Google", "etl", "rest", "oauth2", "Pipeline,Job", "cross_industry", (
        "Cloud Dataflow", "Cloud Data Fusion", "Datastream", "Dataproc",
    )))
    add(_pack("Google", "streaming", "kafka", "oauth2", "Event", "cross_industry", ("Pub/Sub", "Kafka for BigQuery")))
    add(_pack("Google", "ml_platform", "rest", "oauth2", "Model,Endpoint,Dataset", "cross_industry", (
        "Vertex AI", "Vertex Feature Store", "Vertex Experiments",
    )))
    add(_pack("Google", "ai_framework", "rest", "oauth2", "Model,Prompt", "cross_industry", (
        "Gemini Enterprise", "Document AI", "Vision AI", "Natural Language",
    )))
    add(_pack("Google", "bi", "rest", "oauth2", "Report,Explore", "cross_industry", ("Looker", "Looker Studio")))
    add(_pack("Google", "governance", "rest", "oauth2", "Asset,Policy", "cross_industry", ("Dataplex", "Data Catalog")))
    add(_pack("Google", "iam", "rest", "oauth2", "User,Role", "cross_industry", ("Cloud Identity", "IAM")))
    add(_pack("Google", "observability", "rest", "oauth2", "Metric,Log,Trace", "cross_industry", (
        "Cloud Monitoring", "Cloud Logging", "Cloud Trace",
    )))
    add(_pack("Amazon", "data_warehouse", "jdbc", "aws_sigv4", "Table,Column", "cross_industry", (
        "Redshift", "Redshift Serverless", "Aurora", "RDS", "Athena", "DynamoDB",
    )))
    add(_pack("Amazon", "etl", "rest", "aws_sigv4", "Job,Crawler", "cross_industry", (
        "Glue", "Glue DataBrew", "AppFlow", "Data Pipeline", "EMR",
    )))
    add(_pack("Amazon", "streaming", "kafka", "aws_sigv4", "Event,Stream", "cross_industry", (
        "Kinesis Data Streams", "Kinesis Firehose", "Managed Kafka", "SQS", "SNS", "EventBridge",
    )))
    add(_pack("Amazon", "ml_platform", "rest", "aws_sigv4", "Model,Endpoint,TrainingJob", "cross_industry", (
        "SageMaker", "SageMaker Feature Store", "SageMaker Experiments", "SageMaker Pipelines",
    )))
    add(_pack("Amazon", "ai_framework", "rest", "aws_sigv4", "Model,Document", "cross_industry", (
        "Bedrock", "Comprehend", "Textract", "Forecast", "Personalize", "Fraud Detector",
    )))
    add(_pack("Amazon", "bi", "rest", "aws_sigv4", "Dashboard,Dataset", "cross_industry", ("QuickSight",)))
    add(_pack("Amazon", "governance", "rest", "aws_sigv4", "Asset,Classification", "cross_industry", (
        "Glue Catalog", "Lake Formation", "DataZone", "Macie",
    )))
    add(_pack("Amazon", "iam", "rest", "aws_sigv4", "User,Role,Policy", "cross_industry", ("IAM", "Identity Center")))
    add(_pack("Amazon", "observability", "rest", "aws_sigv4", "Metric,Log", "cross_industry", (
        "CloudWatch", "CloudWatch Logs", "X-Ray",
    )))
    add(_pack("Snowflake", "data_warehouse", "jdbc", "key_pair", "Table,View,Share", "cross_industry", (
        "Snowflake", "Snowpark", "Unistore", "Iceberg Tables", "Data Sharing", "Marketplace",
    )))
    add(_pack("Snowflake", "ml_platform", "rest", "key_pair", "Model,Feature", "cross_industry", (
        "Cortex", "Model Registry", "Feature Store",
    )))
    add(_pack("Snowflake", "governance", "jdbc", "key_pair", "Tag,Policy,Object", "cross_industry", (
        "Horizon", "Data Clean Rooms",
    )))
    add(_pack("Databricks", "data_warehouse", "jdbc", "oauth2", "Table,Volume", "cross_industry", (
        "Lakehouse", "Unity Catalog", "Delta Live Tables", "SQL Warehouse",
    )))
    add(_pack("Databricks", "ml_platform", "rest", "oauth2", "Model,Experiment,Feature", "cross_industry", (
        "MLflow", "Feature Store", "Model Serving", "AutoML",
    )))
    add(_pack("Databricks", "etl", "rest", "oauth2", "Pipeline,Job", "cross_industry", ("Workflows", "Lakeflow Connect")))
    add(_pack("Informatica", "etl", "rest", "oauth2", "Mapping,Task", "cross_industry", (
        "PowerCenter", "Intelligent Data Management Cloud", "Cloud Data Integration",
        "Cloud Application Integration", "B2B Gateway", "Mass Ingestion",
    )))
    add(_pack("Informatica", "data_quality", "rest", "oauth2", "Rule,Scorecard", "cross_industry", (
        "Cloud Data Quality", "Data as a Service", "Address Verification",
    )))
    add(_pack("Informatica", "mdm", "rest", "oauth2", "Party,Product", "cross_industry", (
        "MDM Customer 360", "MDM Product 360", "MDM Supplier 360", "MDM Reference 360",
    )))
    add(_pack("Informatica", "governance", "rest", "oauth2", "Asset,Policy", "cross_industry", (
        "Axon", "Enterprise Data Catalog", "Data Marketplace",
    )))
    add(_pack("Fivetran", "etl", "rest", "api_key", "Connector,Destination", "cross_industry", ("Fivetran", "HVR")))
    add(_pack("Airbyte", "etl", "rest", "oauth2", "Source,Destination,Connection", "cross_industry", ("Airbyte",)))
    add(_pack("dbt", "etl", "rest", "api_key", "Model,Test,Job", "cross_industry", ("dbt Cloud", "dbt Core")))
    add(_pack("Talend", "etl", "rest", "oauth2", "Job,Pipeline", "cross_industry", (
        "Data Fabric", "Studio", "Stitch", "Pipeline Designer",
    )))
    add(_pack("Boomi", "etl", "rest", "oauth2", "Process,Atom", "cross_industry", (
        "Integration", "Master Data Hub", "API Management", "Flow", "B2B/EDI",
    )))
    add(_pack("MuleSoft", "etl", "rest", "oauth2", "Application,Api", "cross_industry", (
        "Anypoint", "Composer", "RPA",
    )))
    add(_pack("IBM", "data_warehouse", "jdbc", "basic", "Table,Schema", "cross_industry,financial_services", (
        "Db2", "Db2 Warehouse", "Netezza", "Informix",
    )))
    add(_pack("IBM", "etl", "rest", "basic", "Job,Stage", "cross_industry", (
        "DataStage", "Watsonx.data", "App Connect", "MQ", "Aspera",
    )))
    add(_pack("IBM", "ai_framework", "rest", "api_key", "Model,Prompt", "cross_industry", (
        "watsonx.ai", "Watson Discovery", "Watson NLP", "Watson Assistant",
    )))
    add(_pack("IBM", "ml_platform", "rest", "api_key", "Model,Experiment", "cross_industry", ("Watson Studio", "Watson ML")))
    add(_pack("IBM", "governance", "rest", "basic", "Glossary,Rule", "cross_industry", (
        "Knowledge Catalog", "OpenPages", "Guardium",
    )))
    add(_pack("IBM", "mdm", "rest", "basic", "Party,Agreement", "cross_industry", ("InfoSphere MDM", "Match 360")))
    add(_pack("IBM", "observability", "rest", "api_key", "Trace,Metric", "cross_industry", ("Instana", "Turbonomic")))
    add(_pack("IBM", "streaming", "kafka", "basic", "Event", "cross_industry", ("Event Streams", "StreamSets")))
    add(_pack("Cloudera", "data_warehouse", "jdbc", "kerberos", "Table,Partition", "cross_industry", (
        "Data Platform", "Data Warehouse", "Operational Database",
    )))
    add(_pack("Cloudera", "streaming", "kafka", "kerberos", "Topic,Event", "cross_industry", ("Data Flow", "Kafka")))
    add(_pack("Cloudera", "ml_platform", "rest", "oauth2", "Model,Session", "cross_industry", ("Machine Learning",)))
    add(_pack("Teradata", "data_warehouse", "jdbc", "basic", "Table,Query", "cross_industry", ("Vantage", "QueryGrid")))
    add(_pack("ClickHouse", "data_warehouse", "jdbc", "basic", "Table,View", "cross_industry", ("ClickHouse", "ClickHouse Cloud")))
    add(_pack("DuckDB", "data_warehouse", "jdbc", "none", "Table,View", "cross_industry", ("DuckDB",)))
    add(_pack("PostgreSQL", "data_warehouse", "jdbc", "basic", "Table,View", "cross_industry", ("PostgreSQL", "EnterpriseDB")))
    add(_pack("MySQL", "data_warehouse", "jdbc", "basic", "Table,View", "cross_industry", ("MySQL", "MariaDB")))
    add(_pack("MongoDB", "data_warehouse", "rest", "basic", "Collection,Document", "cross_industry", ("Atlas", "Enterprise")))
    add(_pack("Redis", "feature_store", "rest", "basic", "Key,Vector", "cross_industry", ("Redis", "Redis Cloud")))
    add(_pack("Elastic", "observability", "rest", "api_key", "Index,Document", "cross_industry", (
        "Elasticsearch", "Observability", "Security", "Enterprise Search",
    )))
    add(_pack("Confluent", "streaming", "kafka", "api_key", "Topic,Event", "cross_industry", (
        "Cloud", "Platform", "Stream Designer", "Schema Registry", "Flink",
    )))
    add(_pack("Apache", "streaming", "kafka", "none", "Topic,Event", "cross_industry", (
        "Kafka", "Pulsar", "Flink", "Spark Structured Streaming", "NiFi", "Airflow",
    )))
    add(_pack("Tableau", "bi", "rest", "oauth2", "Workbook,Datasource", "cross_industry", (
        "Cloud", "Server", "Prep", "Pulse",
    )))
    add(_pack("Qlik", "bi", "rest", "oauth2", "App,Space", "cross_industry", ("Sense", "Cloud", "Replicate", "Compose")))
    add(_pack("MicroStrategy", "bi", "rest", "oauth2", "Dossier,Report", "cross_industry", ("Platform", "Cloud")))
    add(_pack("ThoughtSpot", "bi", "rest", "oauth2", "Liveboard,Answer", "cross_industry", ("ThoughtSpot", "Spotter")))
    add(_pack("Sisense", "bi", "rest", "oauth2", "Dashboard,Elasticube", "cross_industry", ("Fusion",)))
    add(_pack("Domo", "bi", "rest", "oauth2", "Card,Dataset", "cross_industry", ("Domo",)))
    add(_pack("Mode", "bi", "rest", "api_key", "Report,Query", "cross_industry", ("Mode",)))
    add(_pack("Sigma", "bi", "rest", "oauth2", "Workbook,Element", "cross_industry", ("Sigma",)))
    add(_pack("Hex", "bi", "rest", "api_key", "Project,Cell", "cross_industry", ("Hex",)))
    add(_pack("DataRobot", "ml_platform", "rest", "api_key", "Project,Model,Deployment", "cross_industry", ("DataRobot",)))
    add(_pack("Dataiku", "ml_platform", "rest", "api_key", "Project,Model", "cross_industry", ("DSS",)))
    add(_pack("H2O", "ml_platform", "rest", "api_key", "Experiment,Model", "cross_industry", ("Driverless AI", "Hydrogen")))
    add(_pack("Weights and Biases", "experiment_tracking", "rest", "api_key", "Run,Artifact", "cross_industry", ("W&B",)))
    add(_pack("Neptune", "experiment_tracking", "rest", "api_key", "Run,Model", "cross_industry", ("Neptune",)))
    add(_pack("MLflow", "experiment_tracking", "rest", "none", "Run,Model", "cross_industry", ("Tracking", "Registry")))
    add(_pack("Feast", "feature_store", "rest", "none", "FeatureView,Entity", "cross_industry", ("Feast",)))
    add(_pack("Tecton", "feature_store", "rest", "oauth2", "FeatureService,FeatureView", "cross_industry", ("Tecton",)))
    add(_pack("Hopsworks", "feature_store", "rest", "api_key", "FeatureGroup,TrainingDataset", "cross_industry", ("Hopsworks",)))
    add(_pack("Census", "reverse_etl", "rest", "oauth2", "Sync,Model", "cross_industry", ("Census",)))
    add(_pack("Hightouch", "reverse_etl", "rest", "oauth2", "Sync,Model", "cross_industry", ("Hightouch",)))
    add(_pack("RudderStack", "cdp", "rest", "api_key", "Event,Profile", "cross_industry", ("RudderStack", "Reverse ETL")))
    add(_pack("Segment", "cdp", "rest", "api_key", "Event,Profile,Audience", "cross_industry", (
        "Connections", "Protocols", "Personas", "Functions",
    )))
    add(_pack("mParticle", "cdp", "rest", "oauth2", "Event,Audience", "cross_industry", ("mParticle",)))
    add(_pack("Tealium", "cdp", "rest", "oauth2", "Audience,Event", "cross_industry", ("AudienceStream", "EventStream", "iQ")))
    add(_pack("Amperity", "cdp", "rest", "oauth2", "Profile,Stitch", "cross_industry", ("Amperity",)))
    add(_pack("Collibra", "governance", "rest", "oauth2", "Asset,Domain,Policy", "cross_industry", (
        "Data Intelligence", "Data Quality", "Data Lineage", "Protect",
    )))
    add(_pack("Alation", "governance", "rest", "oauth2", "Article,Table,Query", "cross_industry", ("Data Catalog", "Analytics")))
    add(_pack("Atlan", "governance", "rest", "api_key", "Asset,Glossary", "cross_industry", ("Atlan",)))
    add(_pack("Great Expectations", "data_quality", "rest", "none", "Expectation,Checkpoint", "cross_industry", ("GX Cloud", "GX Core")))
    add(_pack("Monte Carlo", "data_quality", "rest", "api_key", "Monitor,Incident", "cross_industry", ("Monte Carlo",)))
    add(_pack("Soda", "data_quality", "rest", "api_key", "Check,Dataset", "cross_industry", ("Soda",)))
    add(_pack("Anomalo", "data_quality", "rest", "api_key", "Table,Check", "cross_industry", ("Anomalo",)))
    add(_pack("Bigeye", "data_quality", "rest", "api_key", "Metric,Table", "cross_industry", ("Bigeye",)))
    add(_pack("Precisely", "data_quality", "rest", "oauth2", "Address,Record", "cross_industry", ("Spectrum", "Trillium")))
    add(_pack("Okta", "iam", "rest", "oauth2", "User,Group,App", "cross_industry", ("Workforce Identity", "Customer Identity")))
    add(_pack("CyberArk", "iam", "rest", "oauth2", "Account,Safe", "cross_industry", ("Privilege Cloud", "Endpoint Privilege Manager")))
    add(_pack("SailPoint", "iam", "rest", "oauth2", "Identity,AccessProfile", "cross_industry", ("IdentityNow", "IdentityIQ")))
    add(_pack("Ping", "iam", "rest", "oauth2", "User,Application", "cross_industry", ("PingOne", "PingFederate")))
    add(_pack("ForgeRock", "iam", "rest", "oauth2", "Identity,Journey", "cross_industry", ("Identity Platform",)))
    add(_pack("HashiCorp", "iam", "rest", "api_key", "Secret,Policy", "cross_industry", ("Vault",)))
    add(_pack("Datadog", "observability", "rest", "api_key", "Metric,Log,Trace,Monitor", "cross_industry", (
        "Infrastructure", "APM", "Logs", "RUM", "Security",
    )))
    add(_pack("New Relic", "observability", "rest", "api_key", "Metric,Span,Event", "cross_industry", ("New Relic",)))
    add(_pack("Dynatrace", "observability", "rest", "api_key", "Entity,Metric,Problem", "cross_industry", ("Davis", "Grail")))
    add(_pack("Splunk", "observability", "rest", "api_key", "Index,Event,Metric", "cross_industry", (
        "Enterprise", "Observability Cloud", "SOAR", "Attack Analyzer",
    )))
    add(_pack("Grafana", "observability", "rest", "api_key", "Dashboard,Metric", "cross_industry", (
        "Grafana", "Mimir", "Loki", "Tempo", "OnCall",
    )))
    add(_pack("PagerDuty", "observability", "rest", "api_key", "Incident,Service", "cross_industry", ("PagerDuty",)))
    add(_pack("CrowdStrike", "observability", "rest", "oauth2", "Detection,Device", "cross_industry", ("Falcon",)))
    add(_pack("Palo Alto", "observability", "rest", "api_key", "Alert,Incident", "cross_industry", (
        "Cortex XDR", "Cortex XSOAR", "Prisma Cloud",
    )))
    add(_pack("Bloomberg", "data_warehouse", "sdk", "terminal", "Security,Field,Tick", "financial_services", (
        "Terminal", "B-PIPE", "Data License", "HAPI", "IBVAL", "PORT",
    )))
    add(_pack("LSEG", "data_warehouse", "rest", "oauth2", "Instrument,Quote", "financial_services", (
        "Workspace", "DataScope", "Tick History", "World-Check", "FXall",
    )))
    add(_pack("Murex", "erp", "sdk", "basic", "Trade,Position,Risk", "financial_services", ("MX.3",)))
    add(_pack("Finastra", "erp", "rest", "oauth2", "Account,Payment,Loan", "financial_services", (
        "Fusion Essence", "Fusion Loan IQ", "Fusion Kondor", "Fusion Phoenix", "Fusion Treasury",
        "Fusion Payments", "Fusion Risk", "Fusion Equation",
    )))
    add(_pack("FIS", "erp", "rest", "oauth2", "Account,Transaction,Card", "financial_services", (
        "Profile", "Systematics", "Quantum", "Clear2Pay", "Worldpay", "Trax",
    )))
    add(_pack("Fiserv", "erp", "rest", "oauth2", "Account,Transaction", "financial_services", (
        "DNA", "Signature", "Premier", "Cleartouch", "Commercial Center",
    )))
    add(_pack("Temenos", "erp", "rest", "oauth2", "Customer,Account,Arrangement", "financial_services", (
        "Transact", "Infinity", "Payments", "Financial Crime Mitigation",
    )))
    add(_pack("Thought Machine", "erp", "rest", "oauth2", "Account,Posting", "financial_services", ("Vault Core",)))
    add(_pack("Mambu", "erp", "rest", "oauth2", "Client,Account,Loan", "financial_services", ("Mambu",)))
    add(_pack("nCino", "crm", "rest", "oauth2", "Loan,Deposit,Treasury", "financial_services", ("Bank Operating System",)))
    add(_pack("SWIFT", "streaming", "sdk", "certificate", "Message,Payment", "financial_services", (
        "FIN", "ISO 20022", "gpi", "Alliance Access",
    )))
    add(_pack("Stripe", "erp", "rest", "api_key", "Charge,Customer,Payout", "financial_services,cross_industry", (
        "Payments", "Billing", "Connect", "Treasury", "Radar", "Sigma",
    )))
    add(_pack("Adyen", "erp", "rest", "api_key", "Payment,Settlement", "financial_services", ("Adyen",)))
    add(_pack("Plaid", "etl", "rest", "oauth2", "Transaction,Account,Identity", "financial_services", ("Plaid",)))
    add(_pack("Moody", "ml_platform", "rest", "oauth2", "Score,Entity", "financial_services", (
        "RiskBench", "CreditLens", "Early Warning",
    )))
    add(_pack("S&P", "data_warehouse", "rest", "oauth2", "Entity,Rating,Security", "financial_services", (
        "Capital IQ", "Ratings", "Market Intelligence",
    )))
    add(_pack("FactSet", "data_warehouse", "rest", "oauth2", "Security,Estimate", "financial_services", ("FactSet",)))
    add(_pack("MSCI", "ml_platform", "rest", "oauth2", "Factor,Portfolio", "financial_services", ("Barra", "RiskManager", "ESG")))
    add(_pack("SS&C", "erp", "rest", "oauth2", "Portfolio,Trade,NAV", "financial_services", (
        "Geneva", "Eze", "Algorithmics", "Intrinsiq",
    )))
    add(_pack("Broadridge", "erp", "rest", "oauth2", "Trade,Position,Confirm", "financial_services", (
        "BPS", "Post Trade", "Proxy",
    )))
    add(_pack("Calypso", "erp", "sdk", "basic", "Trade,Risk", "financial_services", ("Calypso",)))
    add(_pack("AxiomSL", "governance", "rest", "oauth2", "Return,Schedule", "financial_services", ("ControllerView",)))
    add(_pack("Wolters Kluwer", "governance", "rest", "oauth2", "Return,Filing", "financial_services", ("OneSumX",)))
    add(_pack("Epic", "erp", "sdk", "oauth2", "Patient,Encounter,Order", "healthcare", (
        "Cadence", "MyChart", "OpTime", "Beacon", "Willow", "Beaker", "Radiant", "Cupid", "Stork",
        "ASAP", "Bugsy", "Healthy Planet", "Resolute", "Grand Central", "Prelude", "Haiku", "Rover",
        "Bones", "Lumens", "Phoenix", "Clarity", "Caboodle", "Cogito",
    )))
    add(_pack("Oracle Health", "erp", "rest", "oauth2", "Patient,Encounter", "healthcare", (
        "Millennium", "PowerChart", "RevElate", "HealtheIntent",
    )))
    add(_pack("MEDITECH", "erp", "rest", "oauth2", "Patient,Order", "healthcare", ("Expanse", "Magic", "Client Server")))
    add(_pack("Veradigm", "erp", "rest", "oauth2", "Patient,Encounter", "healthcare", ("EHR", "Practice Fusion", "FollowMyHealth")))
    add(_pack("athenahealth", "erp", "rest", "oauth2", "Patient,Claim,Appointment", "healthcare", ("athenaOne",)))
    add(_pack("Veeva", "crm", "rest", "oauth2", "Account,Call,Study", "healthcare", (
        "CRM", "Vault Clinical", "Vault Quality", "Vault RIM", "Vault Safety", "Link",
    )))
    add(_pack("IQVIA", "data_warehouse", "rest", "oauth2", "Patient,Prescription,Claim", "healthcare", (
        "Orchestrated Customer Engagement", "MIDAS", "ChannelDynamics",
    )))
    add(_pack("Philips", "observability", "rest", "oauth2", "Alarm,Study,Device", "healthcare", (
        "IntelliVue", "Capsule", "HealthSuite", "Tasy",
    )))
    add(_pack("GE HealthCare", "observability", "rest", "oauth2", "Study,Device,Alarm", "healthcare", (
        "Edison", "Centricity", "Vue PACS", "CARESCAPE",
    )))
    add(_pack("Siemens Healthineers", "observability", "rest", "oauth2", "Study,Device", "healthcare", (
        "Teamplay", "syngo", "Atellica",
    )))
    add(_pack("Change Healthcare", "etl", "rest", "oauth2", "Claim,Eligibility", "healthcare", (
        "Clearinghouse", "InterQual", "Revenue Cycle",
    )))
    add(_pack("Epic", "data_warehouse", "jdbc", "oauth2", "Fact,Dimension", "healthcare", ("Caboodle Warehouse", "Clarity Warehouse")))
    add(_pack("Siemens", "erp", "opcua", "certificate", "Asset,Order,Batch", "manufacturing", (
        "Opcenter", "Teamcenter", "NX", "Tecnomatix", "MindSphere", "Insights Hub", "SIMATIC",
        "PCS 7", "WinCC", "COMOS", "gPROMS",
    )))
    add(_pack("Rockwell", "observability", "opcua", "basic", "Tag,Alarm,Batch", "manufacturing", (
        "FactoryTalk", "Plex", "Fiix", "Emulate3D",
    )))
    add(_pack("PTC", "erp", "rest", "oauth2", "Asset,WorkInstruction", "manufacturing", (
        "Windchill", "ThingWorx", "Kepware", "Vuforia", "Creo",
    )))
    add(_pack("Dassault", "erp", "rest", "oauth2", "Item,BOM,Change", "manufacturing", (
        "3DEXPERIENCE", "DELMIA", "ENOVIA", "SIMULIA", "CATIA",
    )))
    add(_pack("AVEVA", "observability", "opcua", "basic", "Tag,Alarm,Batch", "manufacturing", (
        "PI System", "PI Vision", "Unified Operations Center", "Predictive Analytics",
    )))
    add(_pack("OSIsoft", "streaming", "rest", "basic", "Point,Value", "manufacturing", ("PI Data Archive", "PI AF")))
    add(_pack("AspenTech", "ml_platform", "rest", "oauth2", "Model,Tag", "manufacturing", (
        "Aspen Mtell", "Aspen DMC3", "Aspen HYSYS", "Aspen InfoPlus.21",
    )))
    add(_pack("Honeywell", "observability", "opcua", "basic", "Tag,Alarm", "manufacturing", (
        "Experion", "Forge", "Uniformance",
    )))
    add(_pack("Emerson", "observability", "opcua", "basic", "Tag,Alarm", "manufacturing", (
        "DeltaV", "Ovation", "AMS", "Plantweb",
    )))
    add(_pack("Schneider", "observability", "opcua", "basic", "Tag,Alarm", "manufacturing", (
        "EcoStruxure", "AVEVA edge", "Wonderware",
    )))
    add(_pack("ABB", "observability", "opcua", "basic", "Tag,Alarm", "manufacturing", ("Ability", "800xA", "Ellipse")))
    add(_pack("Infor", "erp", "rest", "oauth2", "Item,Order,Shipment", "manufacturing", (
        "M3", "LN", "CloudSuite Industrial", "WMS", "EAM",
    )))
    add(_pack("Epicor", "erp", "rest", "oauth2", "Part,Job,Shipment", "manufacturing", ("Kinetic", "Prophet 21")))
    add(_pack("Plex", "erp", "rest", "oauth2", "Production,Quality,Inventory", "manufacturing", ("Smart Manufacturing",)))
    add(_pack("QAD", "erp", "rest", "oauth2", "Item,Order,Shipment", "manufacturing", ("Adaptive ERP",)))
    add(_pack("Metabase", "visualization", "rest", "api_key", "Question,Dashboard", "cross_industry", ("Metabase", "Embedded")))
    add(_pack("Apache Superset", "visualization", "rest", "basic", "Chart,Dashboard", "cross_industry", ("Superset",)))
    add(_pack("Redash", "visualization", "rest", "api_key", "Query,Dashboard", "cross_industry", ("Redash",)))
    add(_pack("Evidence", "visualization", "rest", "none", "Page,Query", "cross_industry", ("Evidence",)))
    add(_pack("Lightdash", "visualization", "rest", "api_key", "Chart,Dashboard", "cross_industry", ("Lightdash",)))
    add(_pack("Observable", "visualization", "rest", "api_key", "Notebook,Chart", "cross_industry", ("Observable", "Framework")))
    add(_pack("Plotly", "visualization", "rest", "api_key", "Figure,Dashboard", "cross_industry", ("Dash", "Chart Studio")))
    add(_pack("Streamlit", "visualization", "rest", "none", "App,Widget", "cross_industry", ("Streamlit",)))
    add(_pack("Holistics", "visualization", "rest", "api_key", "Dashboard,Dataset", "cross_industry", ("Holistics",)))
    add(_pack("Omni", "visualization", "rest", "oauth2", "Workbook,Topic", "cross_industry", ("Omni Analytics",)))
    add(_pack("Count", "visualization", "rest", "oauth2", "Canvas,Cell", "cross_industry", ("Count",)))
    add(_pack("SAP", "streaming", "opcua", "certificate", "Tag,Alarm", "manufacturing", ("Plant Connectivity Stream", "Digital Manufacturing Events")))
    add(_pack("UKG", "hcm", "rest", "oauth2", "Employee,Time,Schedule", "cross_industry", ("Pro", "Dimensions", "Ready")))
    add(_pack("ADP", "hcm", "rest", "oauth2", "Worker,Payroll,Time", "cross_industry", ("Workforce Now", "Vantage", "Lyric", "RUN")))
    add(_pack("BambooHR", "hcm", "rest", "api_key", "Employee,TimeOff", "cross_industry", ("BambooHR",)))
    add(_pack("Greenhouse", "hcm", "rest", "api_key", "Candidate,Application,Job", "cross_industry", ("Greenhouse",)))
    add(_pack("Lever", "hcm", "rest", "api_key", "Candidate,Opportunity", "cross_industry", ("Lever",)))
    add(_pack("Zendesk", "crm", "rest", "oauth2", "Ticket,User,Organization", "cross_industry", ("Support", "Sell", "Sunshine")))
    add(_pack("Freshworks", "crm", "rest", "oauth2", "Ticket,Contact", "cross_industry", ("Freshdesk", "Freshsales")))
    add(_pack("Intercom", "crm", "rest", "oauth2", "Conversation,Contact", "cross_industry", ("Intercom",)))
    add(_pack("Shopify", "erp", "rest", "oauth2", "Order,Product,Customer", "cross_industry", ("Admin", "POS", "Plus")))
    add(_pack("BigCommerce", "erp", "rest", "oauth2", "Order,Product,Customer", "cross_industry", ("BigCommerce",)))
    add(_pack("Magento", "erp", "rest", "oauth2", "Order,Product,Customer", "cross_industry", ("Adobe Commerce", "Open Source")))
    add(_pack("Atlassian", "governance", "rest", "oauth2", "Issue,Page,Project", "cross_industry", ("Jira", "Confluence", "Jira Service Management")))
    add(_pack("Asana", "governance", "rest", "oauth2", "Task,Project", "cross_industry", ("Asana",)))
    add(_pack("Monday", "governance", "rest", "oauth2", "Item,Board", "cross_industry", ("monday.com",)))
    add(_pack("Zoom", "observability", "rest", "oauth2", "Meeting,User", "cross_industry", ("Meetings", "Contact Center")))
    add(_pack("Twilio", "streaming", "rest", "api_key", "Message,Call", "cross_industry", ("Communications", "Segment Engage")))
    add(_pack("SendGrid", "reverse_etl", "rest", "api_key", "Message,Contact", "cross_industry", ("Email",)))
    add(_pack("Braze", "cdp", "rest", "api_key", "User,Campaign", "cross_industry", ("Braze",)))
    add(_pack("Iterable", "cdp", "rest", "api_key", "User,Campaign", "cross_industry", ("Iterable",)))
    add(_pack("Klaviyo", "cdp", "rest", "api_key", "Profile,Event", "cross_industry", ("Klaviyo",)))
    add(_pack("HubSpot", "crm", "rest", "oauth2", "Contact,Company,Deal,Ticket", "cross_industry", (
        "CRM", "Marketing Hub", "Sales Hub", "Service Hub", "CMS Hub", "Operations Hub",
    )))
    add(_pack("Zendesk", "bi", "rest", "oauth2", "Explore", "cross_industry", ("Explore",)))
    add(_pack("Coupa", "erp", "rest", "oauth2", "Requisition,Invoice,Supplier", "cross_industry", ("Business Spend",)))
    add(_pack("Ariba", "erp", "odata", "oauth2", "Requisition,Invoice", "cross_industry", ("Network",)))
    add(_pack("Basware", "erp", "rest", "oauth2", "Invoice,Order", "cross_industry", ("AP Automation",)))
    add(_pack("BlackLine", "governance", "rest", "oauth2", "Reconciliation,Task", "financial_services,cross_industry", ("Account Reconciliations", "Transaction Matching")))
    add(_pack("Workiva", "governance", "rest", "oauth2", "Document,Spreadsheet", "financial_services", ("Wdesk",)))
    add(_pack("Anaplan", "bi", "rest", "oauth2", "Model,Module", "cross_industry", ("Anaplan",)))
    add(_pack("OneStream", "bi", "rest", "oauth2", "Cube,Entity", "cross_industry", ("XF",)))
    add(_pack("Board", "bi", "rest", "oauth2", "Capsule,Cube", "cross_industry", ("Board",)))
    add(_pack("Pigment", "bi", "rest", "oauth2", "Block,Metric", "cross_industry", ("Pigment",)))
    add(_pack("Visier", "bi", "rest", "oauth2", "Metric,Employee", "cross_industry", ("People",)))
    add(_pack("Eightfold", "ml_platform", "rest", "oauth2", "Profile,Match", "cross_industry", ("Talent Intelligence",)))
    add(_pack("Phenom", "ml_platform", "rest", "oauth2", "Candidate,Job", "cross_industry", ("Talent Experience",)))
    add(_pack("Cornerstone", "hcm", "rest", "oauth2", "Learning,Performance", "cross_industry", ("OnDemand",)))
    add(_pack("Dayforce", "hcm", "rest", "oauth2", "Employee,Payroll,Time", "cross_industry", ("Dayforce",)))
    add(_pack("Ceridian", "hcm", "rest", "oauth2", "Employee,Payroll", "cross_industry", ("Dayforce HCM",)))
    add(_pack("Paychex", "hcm", "rest", "oauth2", "Employee,Payroll", "cross_industry", ("Flex",)))
    add(_pack("Gusto", "hcm", "rest", "oauth2", "Employee,Payroll", "cross_industry", ("Gusto",)))
    add(_pack("Rippling", "hcm", "rest", "oauth2", "Employee,Device", "cross_industry", ("Rippling",)))
    add(_pack("Deel", "hcm", "rest", "oauth2", "Contract,Invoice", "cross_industry", ("Deel",)))
    add(_pack("Remote", "hcm", "rest", "oauth2", "Employment,Payroll", "cross_industry", ("Remote",)))
    add(_pack("DocuSign", "governance", "rest", "oauth2", "Envelope,Template", "cross_industry", ("eSignature", "CLM")))
    add(_pack("Ironclad", "governance", "rest", "oauth2", "Workflow,Record", "cross_industry", ("Ironclad",)))
    add(_pack("Icertis", "governance", "rest", "oauth2", "Agreement,Clause", "cross_industry", ("Contract Intelligence",)))
    add(_pack("Pega", "ai_framework", "rest", "oauth2", "Case,Decision", "cross_industry,financial_services", (
        "Platform", "Customer Decision Hub", "Customer Service",
    )))
    add(_pack("Appian", "ai_framework", "rest", "oauth2", "Process,Record", "cross_industry", ("Appian",)))
    add(_pack("UiPath", "etl", "rest", "oauth2", "Process,Robot,Queue", "cross_industry", ("Orchestrator", "Automation Cloud")))
    add(_pack("Automation Anywhere", "etl", "rest", "oauth2", "Bot,Queue", "cross_industry", ("Control Room",)))
    add(_pack("Blue Prism", "etl", "rest", "oauth2", "Process,Queue", "cross_industry", ("Blue Prism",)))
    add(_pack("Celonis", "ml_platform", "rest", "oauth2", "Process,Event", "cross_industry", ("Process Mining", "Execution Management")))
    add(_pack("Alteryx", "etl", "rest", "oauth2", "Workflow,Dataset", "cross_industry", ("Designer", "Server", "Analytics Cloud")))
    add(_pack("Trifacta", "data_quality", "rest", "oauth2", "Flow,Recipe", "cross_industry", ("Cloud Dataprep",)))
    add(_pack("Talend", "data_quality", "rest", "oauth2", "Rule,Dataset", "cross_industry", ("Data Quality",)))
    add(_pack("Ataccama", "data_quality", "rest", "oauth2", "Rule,Catalog", "cross_industry", ("ONE",)))
    add(_pack("Profisee", "mdm", "rest", "oauth2", "Entity,Match", "cross_industry", ("Profisee",)))
    add(_pack("Reltio", "mdm", "rest", "oauth2", "Entity,Relation", "cross_industry", ("Reltio",)))
    add(_pack("Semarchy", "mdm", "rest", "oauth2", "Entity,Golden", "cross_industry", ("xDM",)))
    add(_pack("Stibo", "mdm", "rest", "oauth2", "Entity,Product", "cross_industry", ("STEP",)))
    add(_pack("Contentsquare", "bi", "rest", "oauth2", "Session,Zone", "cross_industry", ("Contentsquare",)))
    add(_pack("Amplitude", "bi", "rest", "api_key", "Event,Chart", "cross_industry", ("Amplitude",)))
    add(_pack("Mixpanel", "bi", "rest", "api_key", "Event,Report", "cross_industry", ("Mixpanel",)))
    add(_pack("Heap", "cdp", "rest", "api_key", "Event,User", "cross_industry", ("Heap",)))
    add(_pack("Pendo", "bi", "rest", "api_key", "Event,Guide", "cross_industry", ("Pendo",)))
    add(_pack("Gainsight", "crm", "rest", "oauth2", "Customer,Health", "cross_industry", ("CS",)))
    add(_pack("Totango", "crm", "rest", "oauth2", "Account,Health", "cross_industry", ("Totango",)))
    add(_pack("Clari", "crm", "rest", "oauth2", "Opportunity,Forecast", "cross_industry", ("Clari",)))
    add(_pack("Gong", "crm", "rest", "oauth2", "Call,Deal", "cross_industry", ("Gong",)))
    add(_pack("Outreach", "crm", "rest", "oauth2", "Prospect,Sequence", "cross_industry", ("Outreach",)))
    add(_pack("Salesloft", "crm", "rest", "oauth2", "Person,Cadence", "cross_industry", ("Salesloft",)))
    add(_pack("Marketo", "crm", "rest", "oauth2", "Lead,Campaign", "cross_industry", ("Engagement",)))
    add(_pack("Eloqua", "crm", "rest", "oauth2", "Contact,Campaign", "cross_industry", ("Eloqua",)))
    add(_pack("Braze", "reverse_etl", "rest", "api_key", "User,Canvas", "cross_industry", ("Currents",)))
    add(_pack("Airship", "cdp", "rest", "api_key", "NamedUser,Event", "cross_industry", ("Airship",)))
    add(_pack("OneSignal", "reverse_etl", "rest", "api_key", "User,Notification", "cross_industry", ("OneSignal",)))
    add(_pack("Kafka", "streaming", "kafka", "none", "Topic,Event", "cross_industry", ("Apache Kafka Connect",)))
    add(_pack("Redpanda", "streaming", "kafka", "basic", "Topic,Event", "cross_industry", ("Redpanda",)))
    add(_pack("RabbitMQ", "streaming", "rest", "basic", "Queue,Message", "cross_industry", ("RabbitMQ",)))
    add(_pack("NATS", "streaming", "sdk", "basic", "Subject,Message", "cross_industry", ("NATS", "JetStream")))
    add(_pack("Solace", "streaming", "rest", "basic", "Topic,Message", "cross_industry", ("PubSub+",)))
    add(_pack("TIBCO", "etl", "rest", "basic", "Process,Message", "cross_industry", ("BusinessWorks", "EMS", "Spotfire")))
    add(_pack("Software AG", "etl", "rest", "basic", "Process,Document", "cross_industry", ("webMethods", "ARIS", "Alfabet")))
    add(_pack("Axway", "etl", "rest", "oauth2", "Flow,Api", "cross_industry", ("Amplify",)))
    add(_pack("Kong", "etl", "rest", "api_key", "Service,Route", "cross_industry", ("Gateway", "Konnect")))
    add(_pack("Apigee", "etl", "rest", "oauth2", "Proxy,Product", "cross_industry", ("Apigee",)))
    add(_pack("MuleSoft", "governance", "rest", "oauth2", "Api,Policy", "cross_industry", ("API Manager",)))
    add(_pack("Postman", "governance", "rest", "api_key", "Collection,Monitor", "cross_industry", ("Postman",)))
    add(_pack("Snyk", "observability", "rest", "api_key", "Project,Issue", "cross_industry", ("Snyk",)))
    add(_pack("Wiz", "observability", "rest", "oauth2", "Issue,Asset", "cross_industry", ("Wiz",)))
    add(_pack("Orca", "observability", "rest", "api_key", "Alert,Asset", "cross_industry", ("Orca",)))
    add(_pack("Qualys", "observability", "rest", "basic", "Host,Vulnerability", "cross_industry", ("VMDR",)))
    add(_pack("Tenable", "observability", "rest", "api_key", "Asset,Vulnerability", "cross_industry", ("io", "sc")))
    add(_pack("Rapid7", "observability", "rest", "api_key", "Asset,Vulnerability", "cross_industry", ("InsightVM", "InsightIDR")))
    add(_pack("Snyk", "governance", "rest", "api_key", "Policy,Project", "cross_industry", ("Snyk Code",)))
    # Module-level connectors. These are the objects enterprises bind one at a time.
    add(_pack("SAP S/4", "erp", "odata", "oauth2", "Document", "cross_industry,manufacturing,financial_services", _S4_APIS))
    add(_pack("Epic Clarity", "data_warehouse", "jdbc", "oauth2", "Fact", "healthcare", _EPIC_CLARITY))
    add(_pack("FHIR", "erp", "rest", "oauth2", "Resource", "healthcare", _FHIR))
    add(_pack("ISO 20022", "streaming", "sdk", "certificate", "Message", "financial_services", _ISO20022))
    add(_pack("PI AF", "streaming", "rest", "basic", "Attribute", "manufacturing", _PI_TEMPLATES))
    specs = tuple(groups)
    ids = [spec.id for spec in specs]
    if len(ids) != len(set(ids)):
        seen = set()
        dupes = sorted({item for item in ids if item in seen or seen.add(item)})
        raise RuntimeError(f"duplicate connector ids: {dupes[:12]}")
    covered = {spec.category for spec in specs}
    missing = [name for name in DISPLACED_CLASSES if name not in covered]
    if missing:
        raise RuntimeError(f"catalog missing displaced classes: {missing}")
    if len(specs) < 1000:
        raise RuntimeError(f"catalog has {len(specs)} connectors, 1000 required")
    return specs


_S4_APIS = (
    "API Business Partner", "API Journal Entry", "API Sales Order", "API Billing Document",
    "API Purchase Order", "API Supplier Invoice", "API Product", "API Outbound Delivery",
    "API Inbound Delivery", "API Production Order", "API Planned Order", "API Quality Notification",
    "API Maintenance Order", "API Equipment", "API Functional Location", "API Cost Center",
    "API Profit Center", "API GL Account", "API Asset", "API Bank", "API Payment Advice",
    "API Customer Return", "API Debit Memo", "API Credit Memo", "API Pricing Condition",
    "API Sales Quotation", "API Sales Contract", "API Purchase Requisition", "API Purchase Contract",
    "API Supplier Quotation", "API Physical Inventory", "API Material Document", "API Batch",
    "API Inspection Lot", "API Defect", "API Service Order", "API Service Confirmation",
    "API Workforce Timesheet", "API Workforce Person", "API Commercial Project", "API WBS Element",
    "API Settlement", "API Allocation", "API Universal Journal", "API Cash Flow",
    "API Treasury Position", "API Hedge Accounting", "API Lease Contract", "API Real Estate Contract",
    "API Billing Plan", "API Subscription Contract", "API Provider Contract", "API Convergent Invoicing",
    "API Dispute Case", "API Collections Worklist", "API Credit Management", "API Trade Finance",
    "API Letter of Credit", "API Bank Guarantee", "API Commodity Contract", "API Agriculture Contract",
    "API Utility Contract", "API Meter Reading", "API Billing Simulation", "API Public Sector Fund",
    "API Grant", "API Earmarked Funds", "API Budget Document", "API Travel Request",
    "API Concur Posting", "API Ariba Requisition", "API Fieldglass Timesheet", "API SuccessFactors Replication",
    "API IDoc ORDERS", "API IDoc INVOIC", "API IDoc DESADV", "API IDoc MATMAS",
    "API IDoc DEBMAS", "API IDoc CREMAS", "API IDoc WMMBXY", "API BAPI Goods Movement",
    "API BAPI Acc Document", "API BAPI Sales Order", "API BAPI PO Create", "API BAPI Material Save",
    "API SOAP Credit Commitment", "API SOAP Available to Promise", "API SOAP Pricing",
    "API Event Sales Order Changed", "API Event Journal Entry Posted", "API Event Delivery Created",
    "API Event Invoice Posted", "API Event Quality Decision", "API Event Equipment Installed",
)

_EPIC_CLARITY = (
    "PATIENT", "PAT_ENC", "ORDER_PROC", "ORDER_MED", "CLARITY_DEP", "CLARITY_SER", "CLARITY_EMP",
    "HSP_ACCOUNT", "HSP_TRANSACTIONS", "ARPB_TRANSACTIONS", "COVERAGE", "PAT_ENC_DX",
    "PROBLEM_LIST", "ALLERGY", "MAR_ADMIN_INFO", "IP_FLWSHT_MEAS", "LAB_RESULT", "IMG_STUDY",
    "OR_LOG", "OR_CASE", "ED_IEV", "BILLING_ACCOUNT", "CLM_CLAIM", "REFERRAL", "APPT",
    "ZC_SPECIALTY", "IDENTITY_ID", "HNO_INFO", "ORDER_RESULTS", "FLOWSHEET",
)

_FHIR = (
    "Patient", "Encounter", "Observation", "Condition", "Procedure", "MedicationRequest",
    "MedicationAdministration", "AllergyIntolerance", "DiagnosticReport", "ImagingStudy",
    "ServiceRequest", "Appointment", "Schedule", "Coverage", "Claim", "ExplanationOfBenefit",
    "CarePlan", "Goal", "Immunization", "Device", "Practitioner", "Organization", "Location",
    "Specimen", "DocumentReference", "QuestionnaireResponse", "CareTeam", "RelatedPerson",
    "AdverseEvent", "DetectedIssue",
)

_ISO20022 = (
    "pain.001", "pain.002", "pacs.008", "pacs.009", "pacs.002", "pacs.004", "camt.052", "camt.053",
    "camt.054", "camt.056", "camt.029", "camt.026", "setr.012", "setr.016", "sese.023", "sese.024",
    "semt.002", "seev.031", "seev.033", "colr.003", "fxtr.014", "tsmt.009", "auth.001", "admi.004",
    "head.001", "reda.002",
)

_PI_TEMPLATES = (
    "Boiler Efficiency", "Compressor Health", "Pump Curve", "Heat Exchanger Fouling", "Reactor Temperature",
    "Distillation Overhead", "Tank Inventory", "Flare Flow", "Steam Header", "Cooling Tower",
    "Extruder Torque", "Furnace Draft", "Kiln Shell", "Turbine Vibration", "Generator Load",
    "Conveyor Current", "Crusher Power", "Mill Charge", "Batch Yield", "CIP Conductivity",
    "Clean Room Pressure", "HVAC Valve", "Chiller Load", "Energy Meter", "Water Quality",
    "Emissions Stack", "Safety Interlock", "Line OEE", "Changeover Clock", "SPC Chart",
)


CATALOG: tuple[ConnectorSpec, ...] = _build()
BY_ID: dict[str, ConnectorSpec] = {spec.id: spec for spec in CATALOG}


def get(connector_id: str) -> ConnectorSpec:
    try:
        return BY_ID[connector_id]
    except KeyError as exc:
        raise KeyError(f"unknown connector: {connector_id}") from exc


def search(
    *,
    category: str | None = None,
    industry: str | None = None,
    vendor: str | None = None,
    text: str | None = None,
) -> tuple[ConnectorSpec, ...]:
    needle = text.lower() if text else None
    found = []
    for spec in CATALOG:
        if category and spec.category != category:
            continue
        if industry and industry not in spec.industries:
            continue
        if vendor and spec.vendor.lower() != vendor.lower():
            continue
        if needle and needle not in spec.product.lower() and needle not in spec.vendor.lower() and needle not in spec.id:
            continue
        found.append(spec)
    return tuple(found)
