def print_context_parameters(contexts):
    result = []
    for context in contexts:
        param_list = []
        temp_str = '\n\t'
        for parameter in context.parameters:
            param_list.append("{}: {}".format(
                    parameter, context.parameters[parameter]))
        temp_str += "Name: {}\n\tParameters:\n\t {}".format(
                context.name.split('/')[-1], "\n\t".join(param_list))
        result.append(temp_str)
    result = "\n".join(result)
    return result


def print_parameters(parameters):
    param_list = []
    temp_str = '\n\t'
    for parameter in parameters:
        param_list.append("{}: {}\n\t".format(
                parameter, parameters[parameter]))
        temp_str += "{}".format("\n\t".join(param_list))
    return temp_str


def print_result(result):
    output = "\n========= BEGIN PRINTOUT of DF result =============\n" \
             "Frase in Input (result.query_text):\t {}\n" \
             "Nome dell'intent (intent.display_name):\t {} (Confidence: {})\n" \
             "Contesto (result.output_contexts):\t{}\n" \
             "Frase di risposta (result.fulfillment_text):\t {}\n" \
             "result.action: {}\n" \
             "\n---------------\nParametri (result.parameters): {}\n-----------------"  \
             "\n=========== END PRINTOUT =================".format(
                     result.query_text,
                     result.intent.display_name,
                     result.intent_detection_confidence,
                     print_context_parameters(result.output_contexts),
                     result.fulfillment_text,
                     result.action,
                     print_parameters(result.parameters))
    return output
