import React from 'react'
import classNames from 'classnames'


export const Icon = ({name, text, ...props}) =>
    <i className={'fa fa-' + name} {...props}>{text || null}</i>


export const Spinner = ({className, text, ...props}) =>
    <i className={classNames('fa', 'fa-spinner', 'fa-spin', className)} {...props}>{text || null}</i>


export const Ellipsis = ({className}) =>
    <span className={classNames('animated-ellipsis', className)}></span>
