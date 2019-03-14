<!-- add-breadcrumbs -->
# Stock Reconciliation For Non Serialized Item

Stock Reconciliation is the process of counting and evaluating stock-in-trade,
usually at an organisations year end in order to value the total stock for
preparation of the accounts. In this process actual physical stocks are
checked and recorded in the system. The actual stocks and the stock in the system should be in agreement and accurate. If they are not, you can
use the stock reconciliation tool to reconcile stock balance and value with actuals.

**Difference between Serialized and Non-serialized Items.**

A serial number is a unique, identifying number or group of numbers and
letters assigned to an individual Item. Serialized items are generally high value items for which you need to warranty's and service agreements. Mostly items as machinery, equipments and high-value electronics (computers, printers etc.) are serialized.

Non Serialized items are generally fast moving and low value item, hence doesn't need tracking for each unit. Items like screw, cotton waste, other consumables, stationary products can be categorized as non-serialized.

> Stock Reconciliation option is available for the non serialized Items only. For serialized and batch items, you should create Material Receipt (to increase stock) or Material Issue (to decrease stock) via Stock Entry.

### Opening Stocks

You can upload your opening stock balance in the system using Stock Reconciliation.
Stock Reconciliation will update your stock for a given Item on a given date
for a given Warehouse to the given quantity.

To perform Stock Reconciliation, go to:

> Stock > Tools > Stock Reconciliation > New

#### Step 1: Download Template

A predefined template of an spreadsheet file should be followed for importing item's stock levels and valuations. Open new Stock Reconciliation form to see download option.

<img class="screenshot" alt="Stock Reconciliation" src="./assets/stock-recon-1.png">

#### Step 2: Enter Data in csv file.

<img class="screenshot" alt="Stock Reconciliation" src="./assets/stock-reco-data.png">

The csv format is case-sensitive. Do not edit the headers which are preset in the template. In the Item Code and Warehouse column, enter exact Item Code and Warehouse as created in your Dooks account. For quatity, enter stock level you wish to set for that item, in a specific warehouse.

#### Step 3: Upload file and Enter Values in Stock Reconciliation Form

<img class="screenshot" alt="Stock Reconciliation" src="./assets/stock-recon-2.png">

**Posting Date**

Posting Date will be date when you want uploaded stock to reflect in the report. Posting Date selection option allows you making back dated stock reconcialiation as well.

**Difference Account:**

When making Stock Reconciliation for updating **opening balance**, then you should select Balance Sheet account. By default **Temporary Opening** is created in the chart of account which can be used here.

If you are making Stock Reconciliation for **correcting stock level or valuation of an item**, then you can select any expense account in which you would want difference amount (derived from difference of valuation of item) should be booked. If Expense Account is selected as Difference Account, you will also need to select Cost Center as it is mandatory with any income and expense account selection.

After reviewing saved Reconciliation Data, submit the Stock Reconciliation. On
successful submission, the data will be updated in the system. To check the
submitted data go to stock and view stock level report.

Note: While filling the valuation rates of Items, if you wish to find out the
valuation rates of all items, you can go to stock and click on Item Prices
report. The report will show you all types of rates.

#### Step 4: Review the reconciliation data

<img class="screenshot" alt="Stock Reconciliation" src="./assets/stock-reco-upload.gif">

### Stock Ledger Report

<img class="screenshot" alt="Stock Reconciliation" src="./assets//stock-reco-ledger.png">


**How Stock Reconciliation Works**

Stock Reconciliation on a specific date means balance quantity frozen for that item on reconciliation date, and shall not get affected due to stock entries made before its date.

As per the updated logic, irrespective of receipt/issue entry made for an item, balance quantity as set via Stock Reconciliation will not be affected.

<div class="embed-container">
	<iframe src="https://www.youtube.com/embed/nlHX0ZZ84Lw" frameborder="0" allow="autoplay; encrypted-media" allowfullscreen>
	</iframe>
</div>