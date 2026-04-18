/*---------------------------------------------------------------------
    File Name: custom.js
---------------------------------------------------------------------*/

$(function () {
    "use strict";

    /* Preloader */
    setTimeout(function () {
        $('.loader_bg').fadeToggle();
    }, 1500);

    /* Tooltip */
    $(document).ready(function(){
        $('[data-toggle="tooltip"]').tooltip();
    });

    /* Back to Top */
    $(window).on('scroll', function () {
        var scroll = $(window).scrollTop();
        if (scroll >= 100) {
            $('#back-to-top').addClass('b-show_scrollBut');
        } else {
            $('#back-to-top').removeClass('b-show_scrollBut');
        }
    });

    $('#back-to-top').on('click', function () {
        $('body,html').animate({ scrollTop: 0 }, 600);
    });

    /* Banner owl carousel (legacy, kept for compat) */
    $(document).ready(function () {
        var $owl = $('.banner-rotator-slider');
        if ($owl.length) {
            $owl.owlCarousel({
                items: 1,
                loop: true,
                margin: 10,
                nav: true,
                dots: false,
                navText: ["<i class='fa fa-angle-left'></i>", "<i class='fa fa-angle-right'></i>"],
                autoplay: true,
                autoplayTimeout: 3000,
                autoplayHoverPause: true
            });
        }
    });

    /* Toggle admin sidebar (Bootstrap admin panel) */
    $(document).ready(function () {
        $('#sidebarCollapse').on('click', function () {
            $('#sidebar').toggleClass('active');
            $(this).toggleClass('active');
        });
    });

    /* Product blog carousel */
    if ($('#blogCarousel').length) {
        $('#blogCarousel').carousel({ interval: 5000 });
    }

    /* Contact form validation */
    if (typeof $.validator !== 'undefined') {
        $.validator.setDefaults({
            submitHandler: function () {
                alert("submitted!");
            }
        });
        $(document).ready(function () {
            $('#contact-form').validate({
                rules: {
                    firstname: "required",
                    email: { required: true, email: true },
                    lastname: "required",
                    message: "required",
                    agree: "required"
                },
                messages: {
                    firstname: "Please enter your firstname",
                    email: "Please enter a valid email address",
                    lastname: "Please enter your lastname",
                    message: "Please enter your Message",
                    agree: "Please accept our policy"
                },
                errorElement: "div",
                errorPlacement: function (error, element) {
                    error.addClass("help-block");
                    if (element.prop("type") === "checkbox") {
                        error.insertAfter(element.parent("input"));
                    } else {
                        error.insertAfter(element);
                    }
                },
                highlight: function (element) {
                    $(element).parents(".col-md-4, .col-md-12").addClass("has-error").removeClass("has-success");
                },
                unhighlight: function (element) {
                    $(element).parents(".col-md-4, .col-md-12").addClass("has-success").removeClass("has-error");
                }
            });
        });
    }

});
