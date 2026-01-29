# Orkay Tiles - GHL Widget Configuration

## Popup Form (Onboarding Form)

Use this embedded code for popup lead capture forms on all landing pages:

```html
<iframe
    src="https://api.leadconnectorhq.com/widget/form/DVCroNRXjap5XqKMOzWD"
    style="display:none;width:100%;height:100%;border:none;border-radius:4px"
    id="popup-DVCroNRXjap5XqKMOzWD" 
    data-layout="{'id':'POPUP'}"
    data-trigger-type="alwaysShow"
    data-trigger-value=""
    data-activation-type="alwaysActivated"
    data-activation-value=""
    data-deactivation-type="neverDeactivate"
    data-deactivation-value=""
    data-form-name="ON BOARDING FORM"
    data-height="1216"
    data-layout-iframe-id="popup-DVCroNRXjap5XqKMOzWD"
    data-form-id="DVCroNRXjap5XqKMOzWD"
    title="ON BOARDING FORM"
        >
</iframe>
<script src="https://link.msgsndr.com/js/form_embed.js"></script>
```

## Chat Widget

Use this code for WhatsApp/chat widget on all pages:

```html
<script 
  src="https://widgets.leadconnectorhq.com/loader.js"  
  data-resources-url="https://widgets.leadconnectorhq.com/chat-widget/loader.js" 
  data-widget-id="696e2b7b50385b42732c3050">
</script>
```

## Integration Notes

- Place popup form code before `</body>` tag
- Place chat widget script before `</body>` tag
- Both widgets will load automatically
- Form triggers as popup on page load
- Chat widget appears as floating button

## Form ID Reference

| Widget | ID |
|--------|-----|
| Popup Form | DVCroNRXjap5XqKMOzWD |
| Chat Widget | 696e2b7b50385b42732c3050 |
