# Credit Hold Email Integration Guide

## Overview

The Account Credit Hold module now includes automatic email integration to send detailed credit hold reports to customers along with followup emails.

## 🚀 New Email Features

### 1. **Automatic PDF Attachment**
- **What**: Detailed credit hold report automatically attached to followup emails
- **When**: Sent with followup emails for customers on credit hold
- **Content**: Complete list of outstanding invoices, payment status, and credit hold information

### 2. **Enhanced Email Content**
- **Credit Hold Notice**: Prominent warning banner in email body
- **Total Due Amount**: Clear display of outstanding balance
- **Professional Formatting**: HTML-styled notice with proper styling

### 3. **Configurable Attachment**
- **Per Followup Level**: Configure attachment for specific followup stages
- **Optional Feature**: Enable/disable per followup level as needed
- **Smart Logic**: Only attaches for customers actually on credit hold

## 📋 Configuration Steps

### **Step 1: Configure Followup Levels**

1. Navigate to `Accounting → Configuration → Follow-up Levels`
2. Select or create a followup level
3. Enable the following options:
   - ✅ **Place on Credit Hold**: Places customer on hold
   - ✅ **Attach Credit Hold Report**: Sends PDF with email
   - ✅ **Send Email**: Enables email sending

### **Step 2: Email Template Configuration**

The system automatically enhances emails with:
- Credit hold warning banner
- PDF attachment (if configured)
- Standard followup content

### **Step 3: Test Configuration**

1. Place a test customer on credit hold
2. Manually trigger followup email
3. Verify:
   - Email contains credit hold notice
   - PDF report is attached (if configured)
   - All information is accurate

## 📧 Email Content Examples

### **Email with Credit Hold Notice**

```
⚠️ Credit Hold Notice: Your account is currently on credit hold due to overdue invoices.
Please settle the outstanding amounts to avoid service interruptions.
Total amount due: $1,250.00

Dear Customer,

Exception made if there was a mistake of ours, it seems that the following amount stays unpaid...
[Standard followup content continues]
```

### **PDF Attachment Contents**

The attached PDF includes:
- Customer information and contact details
- Current credit hold status
- Complete list of outstanding invoices
- Payment status and due dates
- Total amounts due and overdue

## 🔧 Advanced Configuration

### **Selective Attachment**

You can configure different behavior per followup level:

#### **First Reminder** (Level 1):
- ❌ Place on Credit Hold: No
- ❌ Attach Credit Hold Report: No
- ✅ Send Email: Yes
- **Result**: Standard reminder email only

#### **Second Reminder** (Level 2):
- ✅ Place on Credit Hold: Yes
- ❌ Attach Credit Hold Report: No
- ✅ Send Email: Yes
- **Result**: Credit hold warning, no PDF attachment

#### **Final Notice** (Level 3):
- ✅ Place on Credit Hold: Yes
- ✅ Attach Credit Hold Report: Yes
- ✅ Send Email: Yes
- **Result**: Credit hold warning + detailed PDF attachment

### **Email Template Customization**

The credit hold notice is automatically added to all email templates. You can customize the notice by modifying the `_get_main_body` method in `account_followup_report.py`.

## 📊 Benefits

### **For Customers:**
- ✅ **Clear Communication**: Explicit notice about credit hold status
- ✅ **Detailed Information**: Complete list of outstanding invoices
- ✅ **Professional Presentation**: Well-formatted PDF documentation
- ✅ **Actionable Content**: Clear payment instructions

### **For Accounting Teams:**
- ✅ **Automation**: No manual attachment required
- ✅ **Consistency**: Standardized communication format
- ✅ **Documentation**: Automatic record of sent reports
- ✅ **Flexibility**: Configurable per followup level

### **For Management:**
- ✅ **Professional Image**: Polished customer communications
- ✅ **Legal Compliance**: Proper documentation of credit hold notices
- ✅ **Audit Trail**: Clear record of customer notifications
- ✅ **Risk Management**: Improved collection processes

## 🛠️ Technical Details

### **Email Generation Process**

1. **Customer Status Check**: Verifies if customer is on credit hold
2. **Followup Level Check**: Confirms attachment is enabled for current level
3. **PDF Generation**: Creates credit hold report if conditions met
4. **Email Enhancement**: Adds credit hold notice to email body
5. **Attachment Addition**: Includes PDF in email attachments
6. **Email Sending**: Processes through standard Odoo email system

### **File Management**

- **Attachment Storage**: PDFs stored as `ir.attachment` records
- **File Naming**: `Credit_Hold_Report_{Customer_Name}.pdf`
- **Retention**: Attachments linked to customer records
- **Security**: Respects standard Odoo access permissions

### **Performance Considerations**

- **On-Demand Generation**: PDFs generated only when needed
- **Caching**: Attachments stored for reuse
- **Background Processing**: Email sending handled by Odoo email queue
- **Resource Optimization**: Minimal impact on system performance

## 🔍 Troubleshooting

### **Common Issues**

#### **PDF Not Attached**
- **Check**: Followup level has "Attach Credit Hold Report" enabled
- **Check**: Customer is actually on credit hold
- **Check**: Email sending is enabled for the followup level

#### **Email Not Enhanced**
- **Check**: Customer credit hold status is current
- **Check**: Followup level configuration is correct
- **Check**: Email templates are not overriding the enhancement

#### **PDF Generation Errors**
- **Check**: Report template exists and is valid
- **Check**: Customer has valid data for report generation
- **Check**: System has sufficient resources for PDF generation

### **Debug Information**

Enable debug mode to see:
- PDF generation process
- Email enhancement steps
- Attachment creation details
- Error messages and stack traces

## 📝 Best Practices

### **Configuration Recommendations**

1. **Gradual Implementation**: Start with higher-level followup reminders
2. **Test Thoroughly**: Verify with test customers before production
3. **Monitor Performance**: Watch email queue and system resources
4. **Customer Feedback**: Gather feedback on email clarity and usefulness

### **Email Content Tips**

1. **Clear Subject Lines**: Include "Credit Hold" for important notices
2. **Prominent Notices**: Use the automatic credit hold banner
3. **Actionable Information**: Include payment methods and contacts
4. **Professional Tone**: Maintain professional but firm communication

### **Attachment Management**

1. **File Size**: Monitor PDF sizes for email delivery
2. **Naming Convention**: Use consistent file naming
3. **Version Control**: Track changes to report templates
4. **Backup Strategy**: Ensure important reports are preserved

## 🔄 Future Enhancements

Planned improvements include:
- **Excel Export Option**: Alternative to PDF attachments
- **Custom Email Templates**: User-configurable email content
- **Multi-language Support**: Localized credit hold notices
- **Advanced Scheduling**: More flexible email timing options
- **Integration APIs**: External system integration capabilities

---

## Support

For technical support or questions about the email integration:
1. Check the Odoo logs for error messages
2. Verify followup level configuration
3. Test with sample customer data
4. Contact system administrator for advanced issues
