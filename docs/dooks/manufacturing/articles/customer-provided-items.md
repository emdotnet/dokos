<!-- add-breadcrumbs -->
# Customer Provided Items

In Contract Manufacturing, in some cases Customer provides specific items as one or few of the BOM components. These items cannot be received using a `Buying Cycle` since that will mean making Customer as a Supplier at the same time and it will go through each doctype in the cycle.

In this feature, Customer Provided Item is received through `Stock Entry` from a `Material Request` with type `Customer provided`.


Here are the steps on how to setup a `Customer Provided` item.

1.  Got to Item Doctype and add a new `Customer Provided` item.

    `Stock > Item >`

2.  In the `Purchase, Replenishment Details` section, check `Is Customer
    Provided` and set a default `Customer`.

    <img alt="Item Purchase Details" class="screenshot" src="../assets/item-purchase.png">

How to receive a `Customer Provided` Items?

1.  If `Production Plan` is used, `Material Request` for this items can be auto
    created.

2. Once a component in a BOM is set as `Customer Provided` and `Material  
   Request` is created from `Production Plan`, it will create both `Material Request` with type `Purchase` and `Customer Provided`. From there, a `Stock Entry` with purpose `Material Receipt` can be created.

3. A `Material Request` can have multiple `Stock Entry` - Material Receipt. It
   will reflect it in the status.

4. Customer will be able to track their `Material Requests` in a Web Portal
   `Material Requests`. The portal is filtered to show only the `Material Request` of the customer.
