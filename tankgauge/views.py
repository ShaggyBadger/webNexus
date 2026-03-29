from django.shortcuts import render


def delivery_form(request):
    return render(request, "tankgauge/delivery_form.html")


def delivery_submit(request):
    if request.method == "POST":
        # Handle form submission logic here
        store_number = request.POST.get("store_number")
        fuel_types = request.POST.getlist("fuel_types")
        # Process data
        # For now, just redirect back to the form or a success page
        return render(
            request,
            "tankgauge/delivery_form.html",
            {"message": "Form submitted successfully!"},
        )
    return render(request, "tankgauge/delivery_form.html")
