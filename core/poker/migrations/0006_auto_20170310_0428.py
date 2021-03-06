# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-10 04:28
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poker', '0005_auto_20170301_2140'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='preset_call',
            field=models.DecimalField(decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name='player',
            name='preset_check',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='player',
            name='preset_checkfold',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='handhistoryaction',
            name='action',
            field=models.CharField(choices=[('BET', 'BET'), ('RAISE_TO', 'RAISE_TO'), ('CALL', 'CALL'), ('CHECK', 'CHECK'), ('FOLD', 'FOLD'), ('TIMEOUT_FOLD', 'TIMEOUT_FOLD'), ('BUY', 'BUY'), ('TAKE_SEAT', 'TAKE_SEAT'), ('LEAVE_SEAT', 'LEAVE_SEAT'), ('SIT_IN', 'SIT_IN'), ('SIT_OUT', 'SIT_OUT'), ('SITOUT_AT_BLINDS', 'SITOUT_AT_BLINDS'), ('SET_AUTO_REBUY', 'SET_AUTO_REBUY'), ('REPORT_BUG', 'REPORT_BUG'), ('WAIT_FOR_BLINDS', 'WAIT_FOR_BLINDS'), ('SET_PRESET_CHECKFOLD', 'SET_PRESET_CHECKFOLD'), ('SET_PRESET_CHECK', 'SET_PRESET_CHECK'), ('SET_PRESET_CALL', 'SET_PRESET_CALL')], max_length=64, null=True),
        ),
        migrations.AlterField(
            model_name='handhistoryevent',
            name='event',
            field=models.CharField(choices=[('DEAL', 'DEAL'), ('POST', 'POST'), ('POST_DEAD', 'POST_DEAD'), ('ANTE', 'ANTE'), ('BET', 'BET'), ('RAISE_TO', 'RAISE_TO'), ('CALL', 'CALL'), ('CHECK', 'CHECK'), ('FOLD', 'FOLD'), ('BUY', 'BUY'), ('TAKE_SEAT', 'TAKE_SEAT'), ('LEAVE_SEAT', 'LEAVE_SEAT'), ('SIT_IN', 'SIT_IN'), ('SIT_OUT', 'SIT_OUT'), ('WIN', 'WIN'), ('RETURN_CHIPS', 'RETURN_CHIPS'), ('OWE_SB', 'OWE_SB'), ('OWE_BB', 'OWE_BB'), ('SET_BLIND_POS', 'SET_BLIND_POS'), ('NEW_HAND', 'NEW_HAND'), ('NEW_STREET', 'NEW_STREET'), ('POP_CARDS', 'POP_CARDS'), ('UPDATE_STACK', 'UPDATE_STACK'), ('REPORT_BUG', 'REPORT_BUG'), ('WAIT_FOR_BLINDS', 'WAIT_FOR_BLINDS'), ('SITOUT_AT_BLINDS', 'SITOUT_AT_BLINDS'), ('SET_AUTO_REBUY', 'SET_AUTO_REBUY'), ('CREATE_TRANSFER', 'CREATE_TRANSFER'), ('ADD_ORBIT_SITTING_OUT', 'ADD_ORBIT_SITTING_OUT'), ('END_HAND', 'END_HAND'), ('SET_TIMEBANK', 'SET_TIMEBANK'), ('RECORD_ACTION', 'RECORD_ACTION'), ('CHAT', 'CHAT'), ('ALERT', 'ALERT'), ('SET_BOUNTY_FLAG', 'SET_BOUNTY_FLAG'), ('REVEAL_HAND', 'REVEAL_HAND'), ('DELAY_COUNTDOWN', 'DELAY_COUNTDOWN'), ('RESET', 'RESET'), ('SET_PRESET_CHECKFOLD', 'SET_PRESET_CHECKFOLD'), ('SET_PRESET_CHECK', 'SET_PRESET_CHECK'), ('SET_PRESET_CALL', 'SET_PRESET_CALL')], max_length=64, null=True),
        ),
    ]
