import { createApp } from "vue";
import PaymentSelector from './PaymentSelector.vue';

frappe.ready(() => {
	const app = createApp(PaymentSelector)
	SetVueGlobals(app)
	app.mount($('#mainview').get(0));
})