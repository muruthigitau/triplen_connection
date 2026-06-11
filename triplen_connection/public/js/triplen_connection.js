$(document).on("ajaxComplete", function () {
	$('.help-box.small.text-muted:contains("Africa/Nairobi")').remove();
	$('.help-box.small.text-muted:contains("Asia/Kolkata")').remove();
});
