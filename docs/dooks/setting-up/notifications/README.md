<!-- add-breadcrumbs -->
# Notifications

You can configure various Notifications in your system to remind you of important activities such as:

1. Completion date of a Task.
2. Expected Delivery Date of a Sales Order.
3. Expected Payment Date.
4. Reminder of followup.
5. If an Order greater than a particular value is received or sent.
6. Expiry notification for a Contract.
7. Completion / Status change of a Task.

For this, you need to setup a Notification.

> Setup > Email > Notification

### Setting Up An Alert

To setup a Notification:

1. Select which Document Type you want watch changes on
2. Define what events you want to watch. Events are:
	1. New: When a new document of the selected type is made.
	2. Save / Submit / Cancel: When a document of the selected type is saved, submitted, cancelled.
	3. Value Change: When a particular value in the selected type changes.
	4. Days Before / Days After: Trigger this alert a few days before or after the **Reference Date.** To set the days, set **Days Before or After**. This can be useful in reminding you of upcoming due dates or reminding you to follow up on certain leads of quotations.
3. Set additional conditions if you want.
4. Set the recipients of this alert. The recipient could either be a field of the document or a list of fixed Email Addresses.
5. Compose the message


### Setting a Subject
::: v-pre
You can retrieve the data for a particular field by using `doc.[field_name]`. To use it in your subject / message, you have to surround it with `{{ }}`. These are called [Jinja](http://jinja.pocoo.org/) tags. So, for example to get the name of a document, you use `{{ doc.name }}`. The below example sends an email on saving a Task with the Subject, "TASK##### has been created"
:::
<img class="screenshot" alt="Setting Subject" src="../assets/notifications/email-alert-subject.png">

### Setting Conditions

Notifications allow you to set conditions according to the field data in your documents. For example, if you want to recieve an Email if a Lead has been saved as "Interested" as it's status, you put `doc.status == "Interested"` in the conditions textbox. You can also set more complex conditions by combining them.

<img class="screenshot" alt="Setting Condition" src="../assets/notifications/email-alert-condition.png">

The above example will send a Notification when a Task is saved with the status "Open" and the Expected End Date for the Task is the date on or before the date on which it was saved on.


### Setting a Message
::: v-pre
You can use both Jinja Tags (`{{ doc.[field_name] }}`) and HTML tags in the message textbox.

	<h3>Order Overdue</h3>

	<p>Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.</p>

	<!-- show last comment -->
	{% if comments %}
	Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
	{% endif %}

	<h4>Details</h4>

	<ul>
	<li>Customer: {{ doc.customer }}
	<li>Amount: {{ doc.total_amount }}
	</ul>
:::
---

### Setting a Value after the Alert is Set

Sometimes to make sure that the Notification is not sent multiple times, you can
define a custom property (via Customize Form) like "Notification Sent" and then
set this property after the alert is sent by setting the **Set Property After Alert**
field.

Then you can use that as a condition in the **Condition** rules to ensure emails are not sent multiple times

<img class="screenshot" alt="Setting Property in Notification" src="../assets/notifications/email-alert-subject.png">

### Example

1. Defining the Criteria
	<img class="screenshot" alt="Defining Criteria" src="../assets/notifications/email-alert-1.png">

1. Setting the Recipients and Message
	<img class="screenshot" alt="Set Message" src="../assets/notifications/email-alert-2.png">


---

# Slack Notifications

If you prefer to have your notifications sent to a dedicated Slack channel, you can also choose the option "Slack" in the channel options and select the appropriate Slack Webhook URL.

### Slack Webhook url

A Slack webhook URL is an URL pointing directly to a Slack channel.

In order to generate webhook URLs, you need to create a new Slack App:

1. Go to https://api.slack.com/slack-apps
2. Click on "Create a Slack App"
	<img class="screenshot" alt="Set Message" src="../assets/notifications/slack_notification_1.png">

3. Give your App a name and choose the right workspace
	Once your app is created, go to the "Incoming Webhooks" section and add a new Webhook to Workspace.  
	<img class="screenshot" alt="Set Message" src="../assets/notifications/slack_notification_2.png">

4. Copy the created link, go back to Dooks and use it to create a new Slack Webhook URL in Integrations > Slack Webhook URL.
	<img class="screenshot" alt="Set Message" src="../assets/notifications/slack_notification_3.png">

5. Select Slack and your Slack channel in the channel and Slack channel fields within your notification
	

### Message Format

Unlike Email messages, Slack doesn't allow HTML formatting.

Instead you can use markdown formatting: [Slack Documentation](https://get.slack.help/hc/en-us/articles/202288908-Format-your-messages)

::: v-pre
Example:
	*Order Overdue*

	Transaction {{ doc.name }} has exceeded Due Date. Please take necessary action.


	{% if comments %}
	Last comment: {{ comments[-1].comment }} by {{ comments[-1].by }}
	{% endif %}

	*Details*

	• Customer: {{ doc.customer }}
	• Amount: {{ doc.grand_total }}
:::

<img class="screenshot" alt="Set Message" src="../assets/notifications/slack_notification_4.png">