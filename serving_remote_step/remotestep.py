

def handler(context,event):
    context.logger.info(event.headers)
    return event.headers
