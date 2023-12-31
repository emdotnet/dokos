<template>
	<div>
		<div class="flex flex-wrap account-preview justify-center" v-if="bank_accounts.length > 1">
			<bank-account-preview
				v-for="(account, i) in bank_accounts"
				:key="i"
				:account="account"
				:selectedAccount="selectedBankAccount"
				@accountSelected="accountSelection"
			/>
		</div>
		<div class="flex flex-wrap account-preview justify-center" v-if="!bank_accounts.length">
			<p>{{ __("Please add at least one company bank account. 'Is company account' must be checked.") }}</p>
		</div>
		<file-uploader
			v-show="!showData && (selectedBankAccount || bank_accounts.length == 1) && upload_type!='plaid'"
			:on_success="onSuccess"
			:allow_multiple="false"
			:method="method"
		/>
		<vue-good-table
			v-show="showData && columns.length && !submitted"
			:columns="columns"
			:rows="rows"
			:fixed-header="false"
			:line-numbers="true"
			styleClass="vgt-table condensed"
			:pagination-options="{
				enabled: true,
				mode: 'records',
				perPage: 10,
				dropdownAllowAll: false,
				nextLabel: __('next'),
				prevLabel: __('prev'),
				rowsPerPageLabel: __('Rows per page'),
				ofLabel: __('of')
			}"
		/>
		<div v-show="submitted" class="flex flex-wrap info-section justify-center align-center">
			<div class="text-muted">
				<div v-show="show_spinner" class="text-center"><i class="fas fa-spinner fa-spin fa-2x"></i></div>
				<p v-html="text_msg"></p>
			</div>
		</div>
	</div>
</template>

<script>
import { VueGoodTable } from 'vue-good-table';
import FileUploader from '../../../../../../frappe/frappe/public/js/frappe/file_uploader/FileUploader.vue';
import BankAccountPreview from './BankAccountPreview.vue';

export default {
	name: 'BankTransactionImporter',
	components: {
		VueGoodTable,
		FileUploader,
		BankAccountPreview
	},
	props: {
		upload_type: {
			type: String,
			default: 'csv'
		},
		bank_accounts: {
			type: Array,
			default: () => []
		}
	},
	data(){
		return {
			columns: [],
			rows: [],
			method: this.upload_type === 'ofx' ?
			'erpnext.accounts.doctype.bank_transaction.bank_transaction_upload.upload_ofx_bank_statement'
			: 'erpnext.accounts.doctype.bank_transaction.bank_transaction_upload.upload_csv_bank_statement',
			showData: false,
			selectedBankAccount: null,
			submitted: false,
			show_spinner: true,
			text_msg: __("Bank transactions creation in progress. Please wait...")
		}
	},
	created() {
		erpnext.bank_transaction.on('add_bank_entries', (include_credit_cards) => {
			this.addBankEntries(include_credit_cards)
			this.submitted = true;
		})

		erpnext.bank_transaction.on('synchronize_via_plaid', () => {
			this.syncPlaidTransactions()
			this.submitted = true;
		})
	},
	methods: {
		onSuccess: function(attachment, r) {
			if (!r.exc && r.message) {
				this.columns = r.message.columns;
				this.rows = r.message.data;
				this.showData = true;

				const credit_card_entries = this.rows.filter(f => f.statement == "Credit Card")
				if (credit_card_entries) {
					erpnext.bank_transaction.trigger('add_credit_card', credit_card_entries.length);
				}
				erpnext.bank_transaction.trigger('add_primary_action');
			}
		},
		addBankEntries(include_credit_cards) {
			if (!this.submitted) {
				const me = this;
				frappe.xcall('erpnext.accounts.doctype.bank_transaction.bank_transaction_upload.create_bank_entries',
					{
						columns: this.columns,
						data: include_credit_cards ? this.rows : this.rows.filter(f => f.statement != "Credit Card"),
						bank_account: this.selectedBankAccount || this.bank_accounts[0].name,
						upload_type: this.upload_type
					}
				).then((result) => {
					if (result.status == "Missing header map") {
						this.show_spinner = false
						const bank_account = this.bank_accounts.filter(f => f.name == (this.selectedBankAccount || this.bank_accounts[0].name))
						this.text_msg = __("Please setup a <a href='{0}'>header mapping for this bank</a> before uploading a csv/xlsx file.", [
							frappe.utils.escape_html("/app/bank/" + bank_account[0].bank)
						])
					} else {
						if (result.success !== 0) {
							frappe.show_alert({message:__("All bank transactions have been created"), indicator:'green'});
						}
						if (result.errors !== 0) {
							frappe.show_alert({message:__("Please check the error log for details about the import errors"), indicator:'red'});
						}
						if (result.duplicates !== 0) {
							const message = __("{0} entries are duplicates and have not been created", [result.duplicates])
							frappe.show_alert({message, indicator:'orange'});
						}
						erpnext.bank_transaction.trigger('close_dialog');
						erpnext.bank_reconciliation.trigger("refresh")
					}
				})
			}
		},
		accountSelection: function(account) {
			this.selectedBankAccount = account;

			if (this.upload_type == 'plaid') {
				erpnext.bank_transaction.trigger('add_plaid_action');
			}
		},
		syncPlaidTransactions() {
			const me = this;
			const bank_account = this.bank_accounts.filter(f => f.name == (this.selectedBankAccount || this.bank_accounts[0].name))
			frappe.xcall('erpnext.erpnext_integrations.doctype.plaid_settings.plaid_settings.sync_transactions', {
				bank: bank_account[0].bank,
				bank_account: bank_account[0].name
			})
			.then((result) => {
				if (!result || result.exc) {
					this.show_spinner = false
					this.text_msg = __(`Please <a href="/app/plaid-settings">link your bank account with Plaid first</a>`)
				} else {
					const msg1 = __("Bank account '{0}' has been synchronized", [bank_account[0].account_name]);
					const msg2 = __("{0} bank transaction(s) created", [result.length]);
					frappe.show_alert({message:msg1, indicator:'green'});
					frappe.show_alert({message:msg2, indicator:'green'});
					erpnext.bank_transaction.trigger('close_dialog');
					erpnext.bank_reconciliation.trigger("refresh")
				}
			})
		}
	}
}
</script>

<style lang='scss'>
@import 'node_modules/vue-good-table/dist/vue-good-table';
@import 'frappe/public/scss/good-grid.scss';

.account-preview {
	margin-bottom: 20px;
}

.info-section {
	min-height: 200px;

	a {
		color: #6195FF;
	}
}
</style>
