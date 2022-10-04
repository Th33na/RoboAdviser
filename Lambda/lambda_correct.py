### Required Libraries ###
from datetime import datetime
from dateutil.relativedelta import relativedelta

## STATIC VARIABLES
RISK_DICT = {
    "low": f'60% bonds (AGG), 40% equities (SPY)',
    "medium": f'40% bonds (AGG), 60% equities (SPY)',
    "high": f'20% bonds (AGG), 80% equities (SPY)',
    "none": f'100% bonds (AGG), 0% equities (SPY)'
}

ERROR_DICT = {
    "low_age": f'Sorry, unable to recommend due to age <= 0',
    "high_age": f'Sorry, unable to recommend due to age > 65',
    "investment_amt": f'Sorry, unable to recommend due to insufficient investment amount',
    "no_risk": f'Unable to recommend. No risk level provided.',
    "unknown_risk": f'Invalid risk level. Accepted Values: None, Low, Medium, High'
}


### Functionality Helper Functions ###
def parse_int(n):
    """
    Securely converts a non-integer value to integer.
    """
    try:
        return int(n)
    except ValueError:
        return float("nan")


def build_validation_result(is_valid, violated_slot, message_content):
    """
    Define a result message structured as Lex response.
    """
    if message_content is None:
        return {"isValid": is_valid, "violatedSlot": violated_slot}

    return {
        "isValid": is_valid,
        "violatedSlot": violated_slot,
        "message": format_message(message_content),
    }


### Dialog Actions Helper Functions ###
def get_slots(intent_request):
    """
    Fetch all the slots and their values from the current intent.
    """
    return intent_request["currentIntent"]["slots"]


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    """
    Defines an elicit slot type response.
    """

    return {
        "sessionAttributes": session_attributes,
        "dialogAction": {
            "type": "ElicitSlot",
            "intentName": intent_name,
            "slots": slots,
            "slotToElicit": slot_to_elicit,
            "message": message,
        },
    }


def confirm_intent(session_attributes, intent_name, slots, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message
        }
    }


def delegate(session_attributes, slots):
    """
    Defines a delegate slot type response.
    """

    return {
        "sessionAttributes": session_attributes,
        "dialogAction": {
            "type": "Delegate",
            "slots": slots
        }
    }


def close(session_attributes, fulfillment_state, message):
    """
    Defines a close slot type response.
    """

    response = {
        "sessionAttributes": session_attributes,
        "dialogAction": {
            "type": "Close",
            "fulfillmentState": fulfillment_state,
            "message": message,
        },
    }

    return response


def format_message(message):
    return {"contentType": "PlainText", "content": message}


### Intents Handlers ###
def recommend_portfolio(intent_request):
    """
    Performs dialog management and fulfillment for recommending a portfolio.
    """
    slots = get_slots(intent_request)
    name = try_ex(lambda: slots['firstName'])
    age = try_ex(lambda: slots['age'])
    investment_amount = try_ex(lambda: slots['investmentAmount'])
    risk_level = try_ex(lambda: slots['riskLevel'])

    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    last_recommendation = try_ex(lambda: session_attributes['last_recommendation'])

    if last_recommendation:
        last_recommendation = json.loads(last_recommendation)

    confirmation_context = try_ex(lambda: session_attributes['confirmationContext'])

    recommendation = investment_recommendation(name, risk_level)

    validation_result = validate_input(age, investment_amount, risk_level)
    if not validation_result['isValid']:
        session_attributes['current_recommendation'] = validation_result['message']['content']
    else:
        session_attributes['current_recommendation'] = recommendation

    current_recommendation = session_attributes['current_recommendation']

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        if age is not None and investment_amount is not None and risk_level is not None:
            validation_result = validate_input(age, investment_amount, risk_level)
            if not validation_result['isValid']:
                slots[validation_result['violatedSlot']] = None
                session_attributes['current_recommendation'] = validation_result['message']['content']
                return elicit_slot(
                    session_attributes,
                    intent_request['currentIntent']['name'],
                    slots,
                    validation_result['violatedSlot'],
                    validation_result['message']
                )

            if confirmation_status == 'Denied':
                # Clear out auto-population flag for subsequent turns.
                try_ex(lambda: session_attributes.pop('confirmationContext'))
                try_ex(lambda: session_attributes.pop('current_recommendation'))
                if confirmation_context == 'AutoPopulate':
                    return elicit_slot(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        {
                            'age': None,
                            'investmentAmount': None,
                            'riskLevel': None
                        },
                        'age',
                        {
                            'contentType': 'PlainText',
                            'content': 'Please input your age'
                        }
                    )

            return delegate(session_attributes, intent_request['currentIntent']['slots'])

        if confirmation_status == 'None':
            # If we are currently auto-populating but have not gotten confirmation, keep requesting for confirmation.
            if (not age and not investment_amount and not risk_level) or confirmation_context == 'AutoPopulate':
                if last_recommendation:
                    session_attributes['confirmationContext'] = 'AutoPopulate'
                    return confirm_intent(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        {
                            'firstName': name,
                            'age': age,
                            'investmentAmount': investment_amount,
                            'riskLevel': risk_level
                        },
                        {
                            'contentType': 'PlainText',
                            'content': 'Please confirm'
                        }
                    )

            # Otherwise, let native DM rules determine how to elicit for slots and/or drive confirmation.
            return delegate(session_attributes, intent_request['currentIntent']['slots'])

        # If confirmation has occurred, continue filling any unfilled slot values or pass to fulfillment.
        if confirmation_status == 'Confirmed':
            # Remove confirmationContext from sessionAttributes so it does not confuse future requests
            try_ex(lambda: session_attributes.pop('confirmationContext'))
            if confirmation_context == 'AutoPopulate':
                if not age:
                    return elicit_slot(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        intent_request['currentIntent']['slots'],
                        'age',
                        {
                            'contentType': 'PlainText',
                            'content': 'How old are you?'
                        }
                    )
                elif not investment_amount:
                    return elicit_slot(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        intent_request['currentIntent']['slots'],
                        'investmentAmount',
                        {
                            'contentType': 'PlainText',
                            'content': 'How much do you want to invest?'
                        }
                    )
                elif not risk_level:
                    return elicit_slot(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        intent_request['currentIntent']['slots'],
                        'riskLevel',
                        {
                            'contentType': 'PlainText',
                            'content': 'What level of investment risk would you like to take? (None, Low, Medium, High)'
                        }
                    )

            return delegate(session_attributes, intent_request['currentIntent']['slots'])

    current_recommendation = session_attributes['current_recommendation']
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': current_recommendation
        }
    )


### investment recoommendation ###
def investment_recommendation(name, risk_level):
    if name is None or risk_level is None:
        return "Unknown"

    recommendation = RISK_DICT.get(risk_level.lower(), "Unknown")
    return f"{name}, given the risk level you chose, we recommend {recommendation}"


### investment recoommendation ###
def error_message(error_state):
    return ERROR_DICT.get(error_state, "Unknown")


### age, investment amount, investment choice input validation
def validate_input(age, investment_amount, risk_level):
    if age is not None:
        int_age = parse_int(age)

        if int_age <= 0:
            return build_validation_result(False, "age", error_message('low_age'))
        if int_age > 65:
            return build_validation_result(False, "age", error_message('high_age'))

    if investment_amount is not None:
        int_investment_amount = parse_int(investment_amount)
        if int_investment_amount < 5000:
            return build_validation_result(False, "investmentAmount", error_message('investment_amt'))

    if risk_level is None:
        return build_validation_result(False, "riskLevel", error_message('no_risk'))
    elif risk_level.lower() not in RISK_DICT.keys():
        return build_validation_result(False, "riskLevel", error_message('unknown_risk'))

    return {'isValid': True}


### Intents Dispatcher ###
def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    intent_name = intent_request["currentIntent"]["name"]

    # Dispatch to bot's intent handlers
    if intent_name == "recommendPortfolio":
        return recommend_portfolio(intent_request)

    raise Exception("Intent with name " + intent_name + " not supported")


### Main Handler ###
def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """

    return dispatch(event)


def try_ex(func):
    """
    Call passed in function in try block. If KeyError is encountered return None.
    This function is intended to be used to safely access dictionary.

    Note that this function would have negative impact on performance.
    """

    try:
        return func()
    except KeyError:
        return None
