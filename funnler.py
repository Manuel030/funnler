import collections

def funnel(data):
    """
    Create SQL code for funnel analysis from input.

    :param data: Dictionary with keys table, start, end, rule_list and query_type.
                 table: the table you want to query
                 start: the start date
                 end: the end date
                 rule_list: Pageviews and events can be used as funnel steps. When multiple values per funnel step are required, comma-seperate them. Events should be specified in this order: "category", "action", "label".
                 query_type: 'ms' for most recent data, 'daterange' else
    :return: SQL code string
    """
    # read in the dictonary
    table = data['table'][0]
    start_date = data['start'][0]
    end_date = data['end'][0]
    rule_list = data['rule_list']
    query_type = data['query_type']

    new_rules = []
    for i in rule_list:
        if len(i) == 1:
            new_rules.append(i[0])
        else:
            new_rules.append(i)

    columns = ['s1.date', 's1.fullVisitorId as s1fullVisitorID', 's1.visitId as s1visitID']
    ordering = []

    def generator(rule_loop, subquery, length, counter, name, column):

        new_subqueries = ''
        while len(rule_loop) > 0:
            # first step
            if len(rule_loop) == length:
                columns.append('s1.firstHit as s1Hit')
                subquery = step(rule_loop[0], counter)
                rule_loop = rule_loop[1:]
                counter += 1
            # all other steps
            else:
                columns.append('s' + str(counter) + '.firstHit as s' + str(counter) + 'Hit')
                ordering.append(
                    '(s' + str(counter - 1) + '.firstHit' + ' < ' + 's' + str(counter) + '.firstHit or s' + str(
                        counter) + '.firstHit is null)')

                new_step = step(rule_loop[0], counter)
                new_subqueries = joining(new_subqueries, new_step, counter, columns, name)
                rule_loop = rule_loop[1:]
                counter += 1
        # base case
        else:
            col_names = []
            for i in new_rules:
                step_name = ' '.join(['Step' + str(find(new_rules, i) + 1)])
                col_names.append(step_name)

            index = []
            for i in range(counter):
                i += 1
                index.append(i)
            names_index = list(zip(map(str, index), col_names))
            column_list = list(map((lambda x: 'count(s' + x[0] + 'Hit) as ' + x[1]), names_index))
            column_str = ', '.join(column_list)

            all_columns = ', '.join(columns)

            concat_ordering = ' AND '.join(ordering)

            comments = ['#STANDARDSQL', '#Query generated by Funnler\n']
            comments = '\n'.join(comments)
            output = ' '.join(['select date,', column_str, 'from (select', all_columns, 'from',
                               '(' + subquery + new_subqueries, 'WHERE', concat_ordering, ')', 'group by date']) #comments,
            return output

    # joining subqueries
    def joining(subquery, new_step, counter, columns, name):
        table = ' '.join([subquery, 'LEFT JOIN', '(' + new_step, 'ON', 's' + str(counter - 1) + '.fullVisitorId', '=',
                          's' + str(counter) + '.fullVisitorId', 'AND', 's' + str(counter - 1) + '.visitId', '=',
                          's' + str(counter) + '.visitId'])
        return table

    # generating the subqueries
    def step(rule, counter):

        cols = 'fullVisitorId, visitId, PARSE_DATE(' + "'%Y%m%d'" + ', date) AS date, MIN(hitNumber) AS firstHit'
        groupby = 'GROUP BY fullVisitorId, visitId, date'

        table = data['table'][0]
        table += ', unnest(hits)'

        if type(rule) == str:  # d.h. es gibt nur eine Regel in diesem funnel step. Muss sich um page handeln
            where = ' '.join(['WHERE page.pagePath =', rule, 'AND totals.visits = 1 AND'])
        else:
            where = ' '.join(['WHERE eventInfo.eventCategory =', rule[0], 'AND eventInfo.eventAction =', rule[1],
                              'and eventInfo.eventLabel =', rule[2], 'AND totals.visits = 1 AND'])

        if query_type == 'ms':
            time = 'parse_date(' + "'%y%m%d'" + ', _table_suffix)=DATE_sub(current_date(), interval 1 day)'
        else:
            time = ' '.join(['_table_suffix between', start_date, ' AND ', end_date])

        return ' '.join(['SELECT', cols, 'FROM', table, where, time, groupby + ') s' + str(counter)])

    # returns the index of an element in a list
    def find(alist, element):
        index = 0
        while index < len(alist):
            if alist[index] == element:
                return index
            index = index + 1
        return False

    the_funnel = generator(new_rules, '', len(new_rules), 1, 's1', columns)
    return the_funnel