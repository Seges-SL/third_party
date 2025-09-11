odoo.define('server_info.auto_update_tests', function (require){
    "use strict";

    var AutoUpdate = require('server_info.auto_update');
    var testUtils = require('web.test_utils');

    QUnit.module('server_info', {}, function(){
        QUnit.module('auto_update');

        QUnit.test("AutoUpdate._change_interval()", function (assert){
            assert.expect(10);

            var widget = new AutoUpdate();
            var test_responses = [2000, '2000', null, 'garbage', false];
            var expected_results = [true, true, false, false, false];
            for(var i = 0; i < test_responses.length; i++)
            {
                widget.interval = 0;
                var result = widget._change_interval(widget, test_responses[i]);
                assert.strictEqual(result, expected_results[i], "For widget.interval = 0, interval = "+test_responses[i]+" of type "+typeof(test_responses[i]));
            }
            for(var i = 0; i < test_responses.length; i++)
            {
                widget.interval = test_responses[i];
                var result = widget._change_interval(widget, test_responses[i]);
                assert.strictEqual(result, false, "For widget.interval = interval, interval = "+test_responses[i]+" of type "+typeof(test_responses[i])+" ");
            }

        });
    });
});