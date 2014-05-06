/**
 * TAPP.module is the base class
 * var TestModule = Module.extend({
 *     sweet: function(){
 *         return 'awesome';
 *     }
 * });
 *
 * var tester_instance = new TestModule();
 *
 * tester_instance.register_page_load_hook('testy', tester_instance.sweet);
 * $.publish('testy'); # 'awesome'
 */

(function () {
    var TRUE = true,
        FALSE = !TRUE,
        ArrayProto = Array.prototype,
        ObjProto = Object.prototype,
        FuncProto = Function.prototype,
        slice = ArrayProto.slice,
        // Shared empty constructor function to aid in prototype-chain creation.
        Ctor = function () {},
        extender = function (obj) {
            $.each(slice.call(arguments, 1), function (i, source) {
                var prop;
                for (prop in source) {
                    if (source[prop] !== void 0) {
                        obj[prop] = source[prop];
                    }
                }
            });
            return obj;
        },
        inherits = function (parent, protoProps, staticProps) {
            var child;

            // The constructor function for the new subclass is either defined by you
            // (the "constructor" property in your `extend` definition), or defaulted
            // by us to simply call `super()`.
            if (protoProps && protoProps.hasOwnProperty('constructor')) {
                child = protoProps.constructor;
            } else {
                child = function () {
                    return parent.apply(this, arguments);
                };
            }

            // Inherit class (static) properties from parent.
            extender(child, parent);

            // Set the prototype chain to inherit from `parent`, without calling
            // `parent`'s constructor function.
            Ctor.prototype = parent.prototype;
            child.prototype = new Ctor();

            // Add prototype properties (instance properties) to the subclass,
            // if supplied.
            if (protoProps) {
                extender(child.prototype, protoProps);
            }

            // Add static properties to the constructor function, if supplied.
            if (staticProps) {
                extender(child, staticProps);
            }

            // Correctly set child's `prototype.constructor`.
            child.prototype.constructor = child;

            // Set a convenience property in case the parent's prototype is needed later.
            child.__super__ = parent.prototype;

            return child;
        },
        // The self-propagating extend function that Backbone classes use.
        extend = function (protoProps, classProps) {
            var child = inherits(this, protoProps, classProps);
            child.extend = this.extend;
            return child;
        },
        // Just a shell
        Klass = function () {};

    // Give Module the ability to be extended
    Klass.extend = extend;

    // So we can make classes that aren't modules
    TAPP.Klass = Klass;

}());
