<!-- add-breadcrumbs -->
# Buying Settings

Buying Settings is where you can define properties which will be applied in the Buying module's transactions. 

![Buying Settings](../assets/buying-settings.png)

Let us look at the various options that can be configured:

### 1. Supplier Naming By

When a Supplier is saved, system generates a unique identity or name for that Supplier which can be used to refer the Supplier in various Buying transactions.

If not configured otherwise, Dooks uses the Supplier's Name as the unique name. If you want to identify Suppliers using names like SUPP-00001, SUPP-00002, or such other patterned series, select the value of Supplier Naming By as "Naming Series".

You can define or select the Naming Series pattern from:

`Setup > Data > Naming Series`

[Click here to know more about defining a Naming Series.](/dooks/setting-up/settings/naming-series.md)

### 2. Default Supplier Group

Configure what should be the value of Supplier Group when a new Supplier is created.

### 3. Default Buying Price List

Configure what should be the value of Buying Price List when a new Buying transaction is created.

### 4. Maintain Same Rate Throughout Purchase Cycle

If this is checked, Dooks will stop you if you change the Item's price in a Purchase Invoice or Purchase Receipt created based on a Purchase Order, i.e. it will maintain the same price throughout the purchase cycle. If there is a requirement where you need the Item's price to change, you should uncheck this option.

### 5. Purchase Order Required

If this option is configured "Yes", Dooks will prevent you from creating a Purchase Invoice or a Purchase Receipt without first creating a Purchase Order.

### 6. Purchase Receipt Required

If this option is configured "Yes", Dooks will prevent you from creating a Purchase Invoice without first creating a Purchase Receipt.

{next}