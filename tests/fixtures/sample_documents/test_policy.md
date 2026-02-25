# ICT Security Policy

**Version:** 2.0
**Effective Date:** January 1, 2026
**Organization:** Caritas Switzerland

---

# 1. Introduction

This ICT Security Policy establishes the standards and requirements for information security within Caritas Switzerland. The policy aims to protect organizational data, systems, and networks from unauthorized access, disclosure, modification, or destruction.

All employees, contractors, volunteers, and third-party service providers must comply with this policy when accessing or using organizational IT resources.

## 1.1 Purpose and Objectives

The primary purpose of this policy is to:
- Establish clear security standards for IT operations
- Define responsibilities for data protection and system security
- Ensure compliance with Swiss data protection laws and international standards
- Minimize the risk of security breaches and data loss

This policy supports Caritas Switzerland's mission by ensuring that sensitive beneficiary information and operational data remain secure and confidential.

## 1.2 Scope

This policy applies to all:
- Employees (full-time, part-time, and temporary)
- Contractors and consultants
- Volunteers with system access
- Third-party service providers with data access

The policy covers all IT resources including computers, mobile devices, network infrastructure, cloud services, and data storage systems.

## 1.3 Definitions

**IT Resources**: All hardware, software, networks, and data owned or managed by Caritas Switzerland.

**Sensitive Data**: Personal information of beneficiaries, donors, employees, and financial records that require protection under Swiss data protection laws.

**Authorized User**: An individual who has been granted access to IT resources in accordance with their role and responsibilities.

---

# 2. Access Control

Access to IT systems and data must be controlled based on the principle of least privilege. Users should only have access to resources necessary for their job functions.

## 2.1 User Authentication

All users must authenticate using unique credentials before accessing IT resources. Multi-factor authentication (MFA) is required for:
- Access to email systems
- Remote access via VPN
- Access to financial systems
- Administrative accounts

User accounts must never be shared between individuals. Generic or shared accounts are prohibited except where explicitly approved by the IT Security Officer.

## 2.2 Password Requirements

All passwords must meet the following minimum requirements:
- At least 12 characters in length
- Include a combination of uppercase letters, lowercase letters, numbers, and special characters
- Not contain dictionary words or personal information
- Not be reused from the previous 5 passwords

Passwords for administrative accounts must be at least 16 characters long.

## 2.3 Password Rotation

Passwords must be changed according to the following schedule:
- Regular user accounts: Every 90 days
- Administrative accounts: Every 60 days
- Service accounts: Every 180 days (with documented approval)

If a password is suspected of being compromised, it must be changed immediately. See Section 5.2 for incident response procedures.

## 2.4 User Roles and Permissions

The organization recognizes the following user roles:

**Standard Users**: Regular employees with access to email, shared drives, and department-specific applications. Standard users cannot install software or modify system settings.

**Power Users**: Department leads and project managers with elevated permissions to access reporting tools, project management systems, and departmental databases.

**IT Administrators**: IT staff with full system access for maintenance, configuration, and support purposes. All administrative actions are logged gemäss Appendix A.

**Security Administrators**: Designated security personnel who manage security tools, review audit logs, and respond to incidents. See Appendix B for security team structure.

## 2.5 Account Provisioning

New user accounts are created only upon receipt of a signed authorization form from the user's manager. The IT department must:
- Verify the authorization before creating the account
- Assign permissions based on the user's role and department
- Provide security awareness training before granting access
- Document the account creation in the access management system

Account access is reviewed quarterly to ensure permissions remain appropriate. See Section 6.1 for the access review process.

## 2.6 Account Deactivation

User accounts must be deactivated or deleted according to the following timeline:
- Immediate deactivation upon termination for cause
- Deactivation within 24 hours of resignation or retirement
- Temporary suspension during extended leave (> 30 days)
- Permanent deletion after 90 days of deactivation

Managers must notify IT immediately when an employee leaves the organization. Refer to Appendix C for the offboarding checklist.

---

# 3. Data Protection

Data protection is critical to maintaining the trust of beneficiaries, donors, and partners. All users must handle data responsibly and in compliance with applicable laws.

## 3.1 Data Classification

All organizational data is classified into one of three categories:

**Public Data**: Information that can be freely shared externally (e.g., published reports, press releases, public website content).

**Internal Data**: Information intended for internal use only (e.g., internal policies, employee directories, project plans). Unauthorized disclosure could cause minor harm.

**Confidential Data**: Sensitive information that must be strictly protected (e.g., beneficiary personal data, donor information, financial records, personnel files). Unauthorized disclosure could cause significant harm or legal liability.

Users must label documents and emails according to their classification level.

## 3.2 Data Encryption

Encryption is required for:
- All confidential data stored on laptops and mobile devices
- All data transmitted over public networks
- Backup media stored off-site
- USB drives and external storage devices containing organizational data

Encryption must use industry-standard algorithms (AES-256 or stronger). The IT department provides approved encryption tools and guidance.

## 3.3 Data Retention

Data must be retained according to the following schedules:

| Data Type | Retention Period | Storage Location |
|-----------|------------------|------------------|
| Beneficiary records | 10 years after case closure | Secure database |
| Donor information | 10 years after last donation | CRM system |
| Financial records | 10 years | Accounting system |
| Email correspondence | 7 years | Email archive |
| Employee records | 10 years after termination | HR system |
| Audit logs | 2 years | Security monitoring system |

After the retention period expires, data must be securely deleted or anonymized. Refer to Appendix D for the data disposal procedure.

## 3.4 Data Backup

Critical systems and data are backed up according to the following schedule:
- Daily incremental backups of all file servers and databases
- Weekly full backups of critical systems
- Monthly backup testing to verify restoration capability

Backup media is encrypted and stored in a secure off-site location. The IT department tests backup restoration procedures quarterly.

## 3.5 Handling Confidential Data

Users must take the following precautions when handling confidential data:
- Store physical documents in locked cabinets when not in use
- Shred confidential documents before disposal
- Lock computer screens when leaving the workstation
- Avoid discussing confidential matters in public areas
- Use secure file sharing methods approved by IT (see Section 4.3)

Confidential data must never be sent via unencrypted email to external recipients.

---

# 4. Acceptable Use

IT resources are provided to support organizational activities. Limited personal use is permitted if it does not interfere with work duties or violate this policy.

## 4.1 Prohibited Activities

The following activities are strictly prohibited:
- Accessing, downloading, or distributing illegal or inappropriate content
- Installing unauthorized software or hardware
- Attempting to bypass security controls or access unauthorized systems
- Using IT resources for personal financial gain
- Sharing login credentials with others
- Connecting unauthorized devices to the network

Violations may result in disciplinary action, up to and including termination.

## 4.2 Internet and Email Use

Internet access is provided for work-related purposes. Users must:
- Avoid visiting websites that pose security risks
- Not download executable files from untrusted sources
- Report suspicious emails to the IT security team (security@caritas.ch)

Email must be used professionally. Personal email should be limited and must comply with all security requirements. Mass email campaigns require approval from the Communications department.

## 4.3 File Sharing and Collaboration

Users must use approved file sharing tools for internal and external collaboration:
- **Internal sharing**: Use the organizational SharePoint or shared network drives
- **External sharing**: Use the approved secure file transfer service

File sharing via personal cloud storage accounts (Dropbox, Google Drive, etc.) is prohibited for organizational data. See Appendix E for approved collaboration tools.

## 4.4 Mobile Devices

Mobile devices (smartphones, tablets, laptops) used for work purposes must:
- Have screen lock enabled with a PIN or biometric authentication
- Install security updates promptly
- Have device encryption enabled
- Be reported immediately if lost or stolen

Personal mobile devices used for work (BYOD) must comply with the Mobile Device Management policy outlined in Appendix F.

## 4.5 Social Media

Employees may use social media for professional purposes with appropriate authorization. When posting on behalf of Caritas Switzerland:
- Obtain approval from the Communications department
- Clearly identify yourself and your affiliation
- Do not disclose confidential information
- Follow brand guidelines and values

Personal social media use during work hours should be minimal and must not disclose organizational confidential information.

---

# 5. Security Incident Management

Security incidents must be reported and handled promptly to minimize damage and prevent recurrence.

## 5.1 Incident Reporting

All users must report suspected security incidents immediately. Examples include:
- Suspected malware infection
- Lost or stolen devices
- Suspected unauthorized access
- Phishing attempts
- Data breaches or leaks

Report incidents to the IT Security Team:
- Email: security@caritas.ch
- Phone: +41 41 419 2222 (24/7 hotline)

## 5.2 Incident Response

The IT Security Team follows a structured incident response process:

1. **Detection and Reporting**: Incident is identified and reported
2. **Assessment**: Security team evaluates severity and impact
3. **Containment**: Immediate actions to limit damage
4. **Investigation**: Root cause analysis and evidence collection
5. **Remediation**: Fix vulnerabilities and restore normal operations
6. **Documentation**: Record incident details and lessons learned

Critical incidents are escalated to senior management within 2 hours. Data breach incidents are reported to authorities as required by Swiss law (within 72 hours).

## 5.3 Malware Protection

All computers and devices must have up-to-date antivirus software installed and running. The IT department manages centralized antivirus updates.

Users must:
- Not disable antivirus software
- Run full system scans weekly
- Report virus warnings immediately
- Avoid opening suspicious email attachments

The IT department conducts monthly security scans of all network systems.

---

# 6. Compliance and Enforcement

Compliance with this policy is mandatory. The organization monitors adherence and investigates violations.

## 6.1 Access Reviews

Access rights are reviewed quarterly by department managers and the IT Security Officer. The review process includes:
- Verification that user permissions match current job responsibilities
- Identification of dormant accounts for deactivation
- Review of administrative access assignments
- Documentation of review findings

Any discrepancies must be corrected within 10 business days.

## 6.2 Security Awareness Training

All users must complete security awareness training:
- Upon hire or initial system access
- Annually thereafter
- After significant policy changes

Training covers:
- Password security and authentication
- Phishing and social engineering
- Data protection and confidentiality
- Incident reporting procedures

Training completion is tracked in the HR system. Users who do not complete required training may have system access suspended.

## 6.3 Audits and Monitoring

The organization conducts regular security audits to verify compliance with this policy. Audits include:
- Review of access logs and system activity
- Vulnerability scanning of network systems
- Penetration testing (annually)
- Review of security controls and configurations

All system activity is logged and monitored. According to Appendix A, logs are retained for 2 years and reviewed regularly for suspicious activity.

## 6.4 Policy Violations

Violations of this policy may result in disciplinary action, including:
- Verbal or written warning
- Temporary suspension of system access
- Mandatory retraining
- Termination of employment or contract
- Legal action if criminal activity is involved

The severity of consequences depends on the nature and impact of the violation. Intentional violations are treated more seriously than accidental mistakes.

## 6.5 Policy Updates

This policy is reviewed annually and updated as needed to address:
- Changes in technology or business operations
- New security threats or vulnerabilities
- Regulatory or legal requirements
- Lessons learned from incidents or audits

Users are notified of policy changes via email and must acknowledge receipt. Significant changes require re-training as specified in Section 6.2.

---

# 7. Responsibilities

Security is a shared responsibility. All users must contribute to maintaining a secure IT environment.

## 7.1 User Responsibilities

All users are responsible for:
- Protecting their login credentials
- Following security best practices
- Reporting security incidents and suspicious activity
- Completing required security training
- Complying with all aspects of this policy

Users who are unsure about security requirements should contact the IT Help Desk for guidance.

## 7.2 Manager Responsibilities

Department managers are responsible for:
- Ensuring team members complete security training
- Authorizing system access for their staff
- Reviewing and approving user access permissions quarterly
- Notifying IT promptly when staff leave or change roles
- Promoting a culture of security awareness

Managers may be held accountable for security incidents resulting from inadequate supervision or failure to enforce policy requirements.

## 7.3 IT Department Responsibilities

The IT department is responsible for:
- Implementing and maintaining security controls
- Managing user accounts and access permissions
- Monitoring systems for security threats
- Responding to security incidents
- Providing security tools and guidance to users
- Conducting security audits and assessments

## 7.4 IT Security Officer Responsibilities

The IT Security Officer oversees the organization's information security program and is responsible for:
- Developing and maintaining security policies
- Managing the incident response process
- Coordinating security audits and assessments
- Reporting security metrics to senior management
- Ensuring compliance with legal and regulatory requirements

The current IT Security Officer is appointed by the Executive Director and reports to the Chief Operating Officer.

---

# Appendix A: Audit Logging Standards

All critical systems must maintain audit logs that record:
- User authentication attempts (successful and failed)
- Changes to user permissions or accounts
- Access to confidential data
- System configuration changes
- Security incidents and alerts

Logs must be protected from unauthorized modification and retained for 2 years. The Security Team reviews logs weekly to identify suspicious patterns or policy violations.

Log entries must include:
- Timestamp (synchronized with central time source)
- User identity
- Source IP address or device identifier
- Action performed
- Result (success or failure)

Automated alerts are configured for critical events such as:
- Failed login attempts (>5 within 15 minutes)
- Access to highly sensitive data
- Changes to security settings
- Privilege escalation attempts

---

# Appendix B: Security Team Structure

The Information Security Team consists of:

**IT Security Officer**: Overall responsibility for information security program and policy compliance

**Security Analysts** (2 positions): Monitor security systems, investigate incidents, conduct vulnerability assessments

**Help Desk Staff** (4 positions): First-line support for security issues and user account management

The Security Team collaborates with:
- IT Infrastructure Team for system hardening
- Legal Department for compliance matters
- HR Department for employee onboarding/offboarding
- Communications Department for public disclosures

Contact information for the Security Team is available on the intranet.

---

# Appendix C: Employee Offboarding Checklist

When an employee leaves the organization, the following steps must be completed:

**Manager Actions** (completed on or before last day):
- [ ] Collect all organizational devices (laptop, phone, access cards)
- [ ] Retrieve any confidential documents or files
- [ ] Notify IT department of departure date
- [ ] Notify HR department of departure date

**IT Department Actions** (completed within 24 hours):
- [ ] Disable network account and email access
- [ ] Revoke VPN and remote access permissions
- [ ] Remove from distribution lists and shared folders
- [ ] Transfer email to manager (if requested)
- [ ] Wipe organizational data from returned devices
- [ ] Update documentation and asset inventory

**HR Department Actions** (completed within 1 week):
- [ ] Conduct exit interview
- [ ] Collect signed confidentiality agreement reminder
- [ ] Process final paycheck and benefits
- [ ] Update organizational directory

This checklist ensures that departing employees cannot access organizational systems or data after their employment ends.

---

# Appendix D: Data Disposal Procedures

When data reaches the end of its retention period, it must be securely disposed of using approved methods.

**Electronic Data Disposal**:
- Delete files from all storage locations (servers, backups, archives)
- Overwrite storage media using DoD 5220.22-M standards (7-pass method minimum)
- For highly sensitive data, physically destroy storage media (shredding or degaussing)

**Physical Document Disposal**:
- Shred confidential documents using cross-cut shredders
- Use locked disposal bins for documents awaiting shredding
- Maintain disposal logs showing date, document type, and staff member responsible

**Device Disposal**:
- Wipe all organizational data before disposing of or donating devices
- Remove and destroy storage media from devices that cannot be reliably wiped
- Obtain certificate of data destruction from third-party disposal vendors

The IT department coordinates all data disposal activities and maintains records for 2 years.

---

# Appendix E: Approved Collaboration Tools

The following tools are approved for file sharing and collaboration:

**Internal Collaboration**:
- Microsoft SharePoint: Document management and team collaboration
- Shared Network Drives: Departmental file storage
- Microsoft Teams: Chat and video conferencing

**External Collaboration**:
- SecureShare Portal: Encrypted file transfer for external partners
- Password-protected SharePoint links: Limited external sharing with expiration dates

**Prohibited Tools**:
- Personal cloud storage (Dropbox, Google Drive, iCloud)
- Consumer file transfer services (WeTransfer, SendAnywhere)
- Unencrypted email attachments for confidential data

Contact the IT department for access to approved tools or questions about file sharing security.

---

# Appendix F: Mobile Device Management (MDM) Policy

Mobile devices accessing organizational email or data must be enrolled in the MDM system. The MDM system enforces:

**Device Requirements**:
- Screen lock with PIN/password (minimum 6 characters) or biometric authentication
- Encryption enabled for device storage
- Automatic security updates
- Remote wipe capability in case of loss or theft

**Application Management**:
- Approved applications only (see approved app list)
- Separation of personal and work data (containerization)
- Restricted installation of apps from untrusted sources

**Compliance Monitoring**:
- Daily compliance checks for all enrolled devices
- Automatic notification to users when devices fall out of compliance
- Access suspension after 7 days of non-compliance

Users with BYOD devices must agree to MDM enrollment and acknowledge that:
- Only organizational data (not personal data) will be remotely wiped if needed
- The organization may view metadata about installed apps for security purposes
- Devices must remain compliant with security requirements to maintain access

Detailed MDM enrollment instructions are available on the IT Help Desk portal.

---

**Document Approval**:
- Approved by: Executive Director
- Review Date: January 1, 2027
- Policy Owner: IT Security Officer

**Version History**:
- v1.0 (Jan 2024): Initial policy
- v2.0 (Jan 2026): Updated password requirements, added BYOD policy, expanded incident response procedures
