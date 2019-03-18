<!-- add-breadcrumbs -->
# Supplier

Suppliers are companies or individuals who provide you with products or services.

You can create a new Supplier from:

`Explore > Buying > Supplier > New 

<img class="screenshot" alt="Supplier Master" src="./assets/supplier-master.png">


In the Supplier master you can add all regular information related to the supplier as well like Tax ID, Billing Currency, Price List and Payment Terms.   So that in all future transactions, these default values will populate in the forms.  

You can also choose a default Supplier Type and add a new type if you want to. 

Each Supplier can have a default price list so that every time when you buy a new item from the supplier, the supplier price list would be updated as well. 


### Contacts and Addresses

Contacts and Addresses in Dokie are stored separately so that you can create multiple Contacts and Addresses for a Supplier. Once Supplier is saved, you will find the option to create Contact and Address for that Supplier.

<img class="screenshot" alt="Supplier Master" src="./assets/supplier-new-address-contact.png">

> Tip: When you select a Supplier in any transaction, Contact for which "Is Primary" field id checked, it will auto-fetch with the Supplier details.

### Integration with Accounts

For all the Supplier, "Creditor" account is set as default payable Account. When Purchase Invoice is created, payable towards the supplier is booked against "Creditors" account.

If you want to customize payable account for the Supplier, you should first add a payable Account in the Chart of Account, and then select that Payable Account in the Supplier master.

<img class="screenshot" alt="Supplier Master" src="./assets/supplier-payable-account.png">

If you don't want to customize payable account, and proceed with default payable account "Creditor", then do not update any value in the Default Supplier Account's table.

> Advanced Tip: Default Payable Account is set in the Company master. If you want to set another account as Account as default for payable instead of Creditors Account, go to Company master, and set that account as "Default Payable Account".

You can add multiple companies in your Dokie instance, and one Supplier can be used across multiple companies. In this case, you should define Companywise Payable Account for the Supplier in the "Default Payable Accounts" table.

<div>
    <div class='embed-container'>
        <iframe src='https://www.youtube.com/embed//zsrrVDk6VBs?start=213' frameborder='0' allowfullscreen>
        </iframe>
    </div>
</div>

### Place Supplier On Hold
In the Supplier form, check the "Block Supplier" checkbox. Next, choose the "Hold Type".

The hold types are as follows:
- Invoices: Dokie will not allow Purchase Invoices or Purchase Orders to be created for the supplier
- Payments: Dokie will not allow Payment Entries to be created for the Supplier
- All: Dokie will apply both hold types above

After selecting the hold type, you can optionally set a release date in the "Release Date" field.

Take note of the following:
- If you do not select a hold type, Dokie will set it to "All"
- If you do not set a release date, Dokie will hold the Supplier indefinitely 

{next}
