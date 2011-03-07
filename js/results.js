$(function() {
	$('.result').each(function() {
		var x = $("#mini_container_x", this).attr('x');
                var y = $("#mini_container_y", this).attr('y');
		//alert(x);
                $(".blank_x", this).css('height', y);
                $(".color_x", this).css('height', x);
                $(".blank_y", this).css('height', x);
                $(".color_y", this).css('height', y);
			});
		}
	);

