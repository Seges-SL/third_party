/** @odoo-module */
var session = require("@web/session").session;
var Widget = require("@web/legacy/js/core/widget").Widget;
var registry = require("@web/core/registry").registry;
var useService = require("@web/core/utils/hooks").useService;
var Component = require("@odoo/owl").Component;
var onWillStart = require("@odoo/owl").onWillStart;
var onWillDestroy = require("@odoo/owl").onWillDestroy;

class AutoUpdate extends Component {
  setup() {
    super.setup();

    this.rpc = useService("rpc");
    this.auto_update_interval = null;
    this.interval = session.interval || 5000;
    onWillStart(() => {
      setTimeout(() => {
        this._update_fields(session);
        this.auto_update_interval = this._get_interval(this, this.interval);
      }, 500);
    });
    onWillDestroy(() => clearInterval(this.auto_update_interval));
  }

  _change_interval(widget, interval) {
    /*
     * Swap interval for new if interval in settings is changed
     */

    if (interval != widget.interval && !isNaN(interval) && interval != null) {
      clearInterval(widget.auto_update_interval);
      widget.interval = interval;
      widget.auto_update_interval = widget._get_interval(widget, interval);
      return true;
    }
    return false;
  }

  _get_interval(widget, interval) {
    /*
     * Returns new interval
     */
    return setInterval(() => {
      widget._getCpuUsage().then((response) => {
        widget._update_fields(response);
        widget._change_interval(widget, response.interval);
      });
    }, interval);
  }

  _update_fields(response) {
    /*
     * Put values from response to corresponding elements in template
     */
    self.$('[name="cpu_usage"]').text(response.cpu_usage);
    self.$('[name="cpu_count"]').text(response.cpu_count);

    self.$('[name="mem_total"]').text(response.mem_total);
    self.$('[name="mem_used"]').text(response.mem_used);
    self.$('[name="mem_used_percent"]').text(response.mem_used_percent);
    self.$('[name="mem_free"]').text(response.mem_free);

    self.$('[name="disk_mem_total"]').text(response.disk_mem_total);
    self.$('[name="disk_mem_used"]').text(response.disk_mem_used);
    self
      .$('[name="disk_mem_used_percent"]')
      .text(response.disk_mem_used_percent);
    self.$('[name="disk_mem_free"]').text(response.disk_mem_free);

    self.$('[name="ip4_info"]').text(response.ip4_info);
    self.$('[name="ip6_info"]').text(response.ip6_info);
  }

  _getCpuUsage() {
    return this.rpc("/web/dataset/call_kw/ir.http/session_info", {
      model: "ir.http",
      method: "session_info",
      args: [session.uid],
      kwargs: {},
    });
  }
}
AutoUpdate.template = "server_info.auto_update";
registry.category("view_widgets").add("auto_update", {
  component: AutoUpdate,
  template: AutoUpdate.template,
});
