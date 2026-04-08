import React from 'react'

import { Button, Form, InputGroup } from 'react-bootstrap'

import {Icon} from '@/components/icons'




export const SearchField = ({onSearch, onChange, text='Search', width=250, bsStyle='default', icon='search', ...props}) => {
    const id = props.id || 'search-field'
    const onSubmit = (event) => {
        event.preventDefault()
        const query = $(`#${id}`).val()
        onSearch(query)
    }
    const search_form_style = `
        form.search-field {
            display: inline-block;
            width: ${width}px;
            vertical-align: bottom;
            margin-bottom: 0px;
        }
        form.search-field .form-group {
            margin-bottom: 0px;
        }
    `
    return <span>
        <style>{search_form_style}</style>
        <form action="#" onSubmit={onSubmit} className="search-field">
            <Form.Group>
                <InputGroup>
                    <Form.Control type="search" id={id} {...props} onChange={() => {onChange($(`#${id}`).val())}}/>
                    <Button bsStyle={bsStyle} onClick={onSubmit} type="submit">
                        <Icon name={icon}/> {text}
                    </Button>
                </InputGroup>
            </Form.Group>
        </form>
    </span>
}
